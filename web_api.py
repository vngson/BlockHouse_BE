"""Authenticated web API extending the existing BlockHouse SQLite database."""
import csv
import io
import os
import secrets
import sqlite3
import hashlib
import json
import sys
import time
from threading import Lock
from urllib.parse import urlsplit
from contextlib import closing
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.local import LocalProxy
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
FROZEN = getattr(sys, 'frozen', False)
DATA_DIR = Path(os.environ.get('BLOCKHOUSE_DATA_DIR') or (Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'BlockHouse' if FROZEN else ROOT / 'data'))
session = LocalProxy(lambda: g.identity)
SCHEMA = "PRAGMA foreign_keys=ON;\nCREATE TABLE IF NOT EXISTS web_users(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, password TEXT NOT NULL);\nCREATE TABLE IF NOT EXISTS web_sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER REFERENCES web_users(id), csrf TEXT NOT NULL, expires INTEGER NOT NULL);\nCREATE TABLE IF NOT EXISTS web_service_state(service_id INTEGER PRIMARY KEY REFERENCES DichVu(ID), active INTEGER NOT NULL DEFAULT 1);\nCREATE TABLE IF NOT EXISTS web_commission_rules(id INTEGER PRIMARY KEY, name TEXT NOT NULL, employee_id INTEGER REFERENCES NhanVien(ID), service_id INTEGER REFERENCES DichVu(ID), kind TEXT NOT NULL, value INTEGER NOT NULL CHECK(value>=0), basis TEXT NOT NULL, starts TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);\nCREATE TABLE IF NOT EXISTS web_order_meta(order_id INTEGER PRIMARY KEY REFERENCES DonHang(ID),discount INTEGER NOT NULL, commission INTEGER NOT NULL,payment TEXT NOT NULL,note TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'paid',request_key TEXT UNIQUE NOT NULL,voided_at TEXT,void_reason TEXT,created_by INTEGER REFERENCES web_users(id));\nCREATE TABLE IF NOT EXISTS web_order_items(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL REFERENCES DonHang(ID),service_id INTEGER REFERENCES DichVu(ID),employee_id INTEGER REFERENCES NhanVien(ID),service_name TEXT NOT NULL,employee_name TEXT NOT NULL,quantity INTEGER NOT NULL,price INTEGER NOT NULL,discount INTEGER NOT NULL,total INTEGER NOT NULL,commission INTEGER NOT NULL,rule_snapshot TEXT NOT NULL);\nCREATE INDEX IF NOT EXISTS web_items_order ON web_order_items(order_id);\nCREATE VIEW IF NOT EXISTS web_employees AS SELECT ID id,Ten name,COALESCE(SDT,'') phone,TrangThai active FROM NhanVien;\nCREATE VIEW IF NOT EXISTS web_services AS SELECT s.ID id,s.Ten name,s.Gia price,COALESCE(w.active,1) active FROM DichVu s LEFT JOIN web_service_state w ON s.ID=w.service_id;\nCREATE VIEW IF NOT EXISTS web_orders AS SELECT d.ID id,replace(d.NgayGio,' ','T')||'+07:00' created_at,CAST(ROUND(COALESCE(d.TongTien,0)) AS INTEGER) total,COALESCE(w.discount,0) discount,CASE WHEN w.order_id IS NULL THEN CAST(ROUND(COALESCE(d.TongTien,0)) AS INTEGER) ELSE w.commission END commission,COALESCE(w.payment,'unknown') payment,COALESCE(w.note,'') note,COALESCE(w.status,'paid') status,w.request_key,w.voided_at,w.void_reason,w.created_by,(w.order_id IS NULL) legacy FROM DonHang d LEFT JOIN web_order_meta w ON d.ID=w.order_id;\nCREATE TRIGGER IF NOT EXISTS web_employee_insert INSTEAD OF INSERT ON web_employees BEGIN INSERT INTO NhanVien(Ten,SDT,TrangThai,ThuNhap,created_at,updated_at) VALUES(NEW.name,NEW.phone,NEW.active,0,datetime('now'),datetime('now')); END;\nCREATE TRIGGER IF NOT EXISTS web_employee_update INSTEAD OF UPDATE ON web_employees BEGIN UPDATE NhanVien SET Ten=NEW.name,SDT=NEW.phone,TrangThai=NEW.active,updated_at=datetime('now') WHERE ID=OLD.id; END;\nCREATE TRIGGER IF NOT EXISTS web_service_insert INSTEAD OF INSERT ON web_services BEGIN INSERT INTO DichVu(Ten,Gia,created_at,updated_at) VALUES(NEW.name,NEW.price,datetime('now'),datetime('now')); INSERT INTO web_service_state(service_id,active) VALUES(last_insert_rowid(),NEW.active); END;\nCREATE TRIGGER IF NOT EXISTS web_service_update INSTEAD OF UPDATE ON web_services BEGIN UPDATE DichVu SET Ten=NEW.name,Gia=NEW.price,updated_at=datetime('now') WHERE ID=OLD.id; INSERT INTO web_service_state(service_id,active) VALUES(OLD.id,NEW.active) ON CONFLICT(service_id) DO UPDATE SET active=NEW.active; END;\n"


def today():
    # Windows may not have an IANA timezone database. Vietnam has a fixed UTC+7 offset.
    from datetime import timezone, timedelta
    return datetime.now(timezone(timedelta(hours=7))).isoformat(timespec='seconds')


def integer(value, label, minimum=0, maximum=1_000_000_000):
    if isinstance(value, bool):
        raise ValueError(f'{label} không hợp lệ.')
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number != number.to_integral_value() or not minimum <= number <= maximum:
            raise ValueError()
        return int(number)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'{label} phải là số nguyên từ {minimum:,} đến {maximum:,}.')


def text(value, label, limit=120):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f'{label} cần từ 1 đến {limit} ký tự.')
    return value.strip()



DEFAULT_COMMISSION_SNAPSHOT = 'Mặc định · 100% · sau giảm giá'


def upgrade_unconfigured_commissions(connection, database):
    # Only the old no-rule marker proves that zero was a fallback, not a saved rate.
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        affected = connection.execute("SELECT DISTINCT order_id FROM web_order_items WHERE rule_snapshot=? AND commission=0", ('Chưa cấu hình · 0đ',)).fetchall()
        if not affected:
            return
        from backup import snapshot
        backup = Path(database).with_name(Path(database).name + '.before-default-commission-100-' + secrets.token_hex(6) + '.bak')
        snapshot(database, backup)
        connection.execute("UPDATE web_order_items SET commission=total,rule_snapshot=? WHERE rule_snapshot=? AND commission=0", (DEFAULT_COMMISSION_SNAPSHOT, 'Chưa cấu hình · 0đ'))
        connection.executemany('UPDATE web_order_meta SET commission=(SELECT SUM(commission) FROM web_order_items WHERE order_id=web_order_meta.order_id) WHERE order_id=?', affected)


def register_web_api(app, database):
    """Add browser API to the existing BE and its existing SQLite database."""
    database = str(database)
    settings_path = Path(app.config.get('WEB_SETTINGS_PATH') or ((Path(sys.executable).parent if FROZEN else ROOT) / 'backend-config.json'))
    settings = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
    origins = set(app.config.get('WEB_ALLOWED_ORIGINS', settings.get('allowed_origins', [])))
    origins.update(filter(None, os.getenv('BLOCKHOUSE_ALLOWED_ORIGINS', '').split(',')))
    for origin in origins:
        parsed = urlsplit(origin)
        if parsed.scheme not in ('http', 'https') or origin != f'{parsed.scheme}://{parsed.netloc}' or parsed.username or '*' in origin:
            raise ValueError('allowed_origins requires exact origins, without paths or wildcards.')
    app.config.update(WEB_DATABASE=database, MAX_CONTENT_LENGTH=128 * 1024,
                      ALLOWED_ORIGINS=origins,
                      ALLOWED_HOSTS=set(settings.get('allowed_hosts', [])) | {'localhost', '127.0.0.1', '::1'})
    from backup import Backups
    backup_settings = settings.get('backup', {})
    backup_folder = app.config.get('WEB_BACKUP_DIR') or backup_settings.get('directory') or str(Path(database).parent / 'backups')
    if not Path(backup_folder).is_absolute():
        raise ValueError('Backup directory must be an absolute path.')
    app.extensions['blockhouse_backups'] = Backups(database, backup_folder, backup_settings.get('keep', 30))
    app.config['WEB_BACKUP_HOURS'] = max(1, min(24, int(backup_settings.get('interval_hours', 6))))
    # Desktop content is bundled locally, not fetched from this domain.
    app.config['ALLOWED_ORIGINS'].add('https://blockhouse.desktop')
    failures, failure_lock = {}, Lock()
    with closing(sqlite3.connect(database)) as connection:
        if not app.config.get('TESTING') and not connection.execute("SELECT name FROM sqlite_master WHERE name='web_users'").fetchone():
            backup_path = Path(database).with_name(Path(database).name + '.before-web.bak')
            if not backup_path.exists():
                with closing(sqlite3.connect(backup_path)) as backup:
                    connection.backup(backup)
        # Refresh the derived view atomically; original orders and saved commissions stay intact.
        connection.executescript('BEGIN IMMEDIATE;\n' + SCHEMA.replace('CREATE VIEW IF NOT EXISTS web_orders', 'DROP VIEW IF EXISTS web_orders;\nCREATE VIEW web_orders') + 'COMMIT;')
        upgrade_unconfigured_commissions(connection, database)

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['WEB_DATABASE'], timeout=10)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys=ON')
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        if 'db' in g:
            g.db.close()

    def rows(sql, args=()):
        return [dict(row) for row in db().execute(sql, args).fetchall()]

    def protected(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get('user'):
                return jsonify(error='Vui lòng đăng nhập.'), 401
            return fn(*args, **kwargs)
        return wrapper

    @app.before_request
    def csrf():
        g.identity = {}
        g.token = None
        if urlsplit('http://' + request.host).hostname not in app.config['ALLOWED_HOSTS']:
            return jsonify(error='Địa chỉ máy chủ không được phép.'), 403
        if request.path.startswith('/api/v1/') and request.path.rstrip('/') != '/api/v1/health':
            return jsonify(error='API WPF cũ đã tắt. Hãy dùng BlockHouse Desktop mới.'), 410
        if request.path in ('/users', '/houses', '/bookings'):
            return jsonify(error='Không tìm thấy API.'), 404
        origin = request.headers.get('Origin')
        if origin and origin != request.host_url.rstrip('/') and origin not in app.config['ALLOWED_ORIGINS']:
            return jsonify(error='Website chưa được cho phép trong backend-config.json.'), 403
        if origin and not request.path.startswith('/api/web/'):
            return jsonify(error='Use the authenticated /api/web API.'), 403
        if request.method == 'OPTIONS' and request.path.startswith('/api/web/'):
            return '', 204
        bearer = request.headers.get('Authorization', '')
        if bearer.startswith('Bearer '):
            token = bearer[7:]
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            matches = rows('SELECT s.*,u.name FROM web_sessions s LEFT JOIN web_users u ON s.user_id=u.id WHERE token_hash=? AND expires>?', (token_hash, int(time.time())))
            if matches:
                g.token = token
                s = matches[0]
                g.identity = {'csrf': s['csrf']}
                if s['user_id']:
                    g.identity['user'] = {'id': s['user_id'], 'name': s['name']}
        if request.path.startswith('/api/web/') and request.method != 'GET':
            if not session.get('csrf') or not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session['csrf']):
                return jsonify(error='Phiên đã hết hạn. Vui lòng tải lại trang.'), 403
        if request.path.startswith('/api/web/') and request.method == 'POST' and not request.is_json:
            return jsonify(error='Yêu cầu phải là JSON.'), 415
        if request.path.startswith('/api/web/') and request.method == 'POST' and not isinstance(request.get_json(silent=True), dict):
            return jsonify(error='Nội dung yêu cầu phải là một đối tượng JSON.'), 400

    @app.after_request
    def headers(response):
        origin = request.headers.get('Origin')
        if request.path.startswith('/api/web/') and origin and origin in app.config['ALLOWED_ORIGINS']:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Vary'] = 'Origin'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, X-CSRF-Token'
            response.headers['Access-Control-Max-Age'] = '600'
            response.headers['Access-Control-Allow-Private-Network'] = 'true'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        if request.path.startswith('/api/web/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(sqlite3.IntegrityError)
    def conflict(_error):
        return jsonify(error='Dữ liệu không hợp lệ hoặc bị trùng. Vui lòng tải lại và thử lại.'), 409

    @app.get('/api/web/health')
    def health():
        return jsonify(app='BlockHouse', api_version=2)

    def limit_attempts(scope):
        key = (scope, request.remote_addr)
        now = time.time()
        with failure_lock:
            attempts = [t for t in failures.get(key, []) if now-t < 300]
            if len(attempts) >= 10:
                return jsonify(error='Bạn thử quá nhiều lần. Vui lòng chờ 5 phút.'), 429
            failures[key] = attempts + [now]

    @app.get('/api/web/session')
    def get_session():
        session.setdefault('csrf', secrets.token_hex(24))
        if app.config.get('WEB_DEMO', False):
            session['user'] = {'id': 1, 'name': 'Chủ shop · Demo'}
        token = secrets.token_urlsafe(32)
        with db():
            if g.token:
                db().execute('DELETE FROM web_sessions WHERE token_hash=?', (hashlib.sha256(g.token.encode()).hexdigest(),))
            db().execute('DELETE FROM web_sessions WHERE expires<=?', (int(time.time()),))
            db().execute('INSERT INTO web_sessions(token_hash,user_id,csrf,expires) VALUES(?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), session.get('user', {}).get('id'), session['csrf'], int(time.time())+12*3600))
        return jsonify(user=session.get('user'), csrf=session['csrf'], token=token, setup=not rows('SELECT id FROM web_users LIMIT 1'), demo=app.config.get('WEB_DEMO', False))

    @app.post('/api/web/setup')
    def setup():
        if request.remote_addr not in ('127.0.0.1', '::1'):
            return jsonify(error='Chỉ tạo tài khoản lần đầu trên máy chủ shop.'), 403
        data = request.get_json()
        name = text(data.get('name'), 'Tên đăng nhập', 60)
        password = text(data.get('password'), 'Mật khẩu', 200)
        if len(password) < 10:
            raise ValueError('Mật khẩu cần ít nhất 10 ký tự.')
        with db():
            db().execute('BEGIN IMMEDIATE')
            if rows('SELECT id FROM web_users LIMIT 1'):
                return jsonify(error='Đã có tài khoản quản trị.'), 409
            cur = db().execute('INSERT INTO web_users(name,password) VALUES(?,?)', (name, generate_password_hash(password)))
        session.clear()
        session.update(user={'id': cur.lastrowid, 'name': name}, csrf=secrets.token_hex(24))
        return get_session()

    @app.post('/api/web/login')
    def login():
        data = request.get_json()
        limited = limit_attempts('login')
        if limited:
            return limited
        users = rows('SELECT * FROM web_users WHERE name=?', (str(data.get('name', '')),))
        if not users or not check_password_hash(users[0]['password'], str(data.get('password', ''))):
            return jsonify(error='Tên đăng nhập hoặc mật khẩu chưa đúng.'), 401
        with failure_lock:
            failures.pop(('login', request.remote_addr), None)
        session.clear()
        session.update(user={'id': users[0]['id'], 'name': users[0]['name']}, csrf=secrets.token_hex(24))
        return get_session()

    @app.post('/api/web/logout')
    def logout():
        if g.token:
            with db():
                db().execute('DELETE FROM web_sessions WHERE token_hash=?', (hashlib.sha256(g.token.encode()).hexdigest(),))
        session.clear()
        return jsonify(ok=True)

    @app.post('/api/web/account/password')
    @protected
    def change_password():
        limited = limit_attempts('password')
        if limited:
            return limited
        data = request.get_json()
        password = data.get('new_password')
        if not isinstance(password, str) or not 10 <= len(password) <= 200 or not password.strip():
            raise ValueError('Mật khẩu mới cần từ 10 đến 200 ký tự.')
        user_id = session['user']['id']
        with db():
            db().execute('BEGIN IMMEDIATE')
            user = rows('SELECT password FROM web_users WHERE id=?', (user_id,))
            if not user or not check_password_hash(user[0]['password'], str(data.get('current_password', ''))):
                return jsonify(error='Mật khẩu hiện tại chưa đúng.'), 400
            db().execute('UPDATE web_users SET password=? WHERE id=?', (generate_password_hash(password), user_id))
            db().execute('DELETE FROM web_sessions WHERE user_id=?', (user_id,))
        with failure_lock:
            failures.pop(('password', request.remote_addr), None)
        session['csrf'] = secrets.token_hex(24)
        return get_session()

    @app.get('/api/web/maintenance')
    @protected
    def maintenance():
        return jsonify(backup=app.extensions['blockhouse_backups'].status())

    @app.post('/api/web/maintenance/backup')
    @protected
    def backup_now():
        manager = app.extensions['blockhouse_backups']
        try:
            filename = manager.create()
        except (OSError, sqlite3.Error, RuntimeError):
            return jsonify(error='Không tạo được backup. Kiểm tra dung lượng và quyền ghi thư mục backup.'), 503
        return jsonify(filename=filename, backup=manager.status())

    @app.get('/api/web/catalog')
    @protected
    def catalog():
        return jsonify(employees=rows('SELECT * FROM web_employees ORDER BY active DESC, name'),
                       services=rows('SELECT * FROM web_services ORDER BY active DESC, name'),
                       rules=rows('SELECT r.*, e.name employee_name,s.name service_name FROM web_commission_rules r LEFT JOIN web_employees e ON e.id=r.employee_id LEFT JOIN web_services s ON s.id=r.service_id ORDER BY r.id DESC'))

    @app.post('/api/web/catalog/<kind>')
    @protected
    def save_catalog(kind):
        if kind not in ('employees', 'services'):
            return jsonify(error='Không tìm thấy danh mục.'), 404
        data = request.get_json()
        name = text(data.get('name'), 'Tên')
        active = integer(data.get('active', 1), 'Trạng thái', 0, 1)
        extra = text(data.get('phone') or ' ', 'Số điện thoại', 30) if kind == 'employees' and data.get('phone', '').strip() else ''
        if kind == 'services':
            extra = integer(data.get('price'), 'Giá dịch vụ')
        column = 'phone' if kind == 'employees' else 'price'
        kind = 'web_' + kind
        with db():
            if data.get('id'):
                if not rows(f'SELECT id FROM {kind} WHERE id=?', (integer(data['id'], 'ID', 1),)):
                    raise ValueError('Danh mục không còn tồn tại.')
                cur = db().execute(f'UPDATE {kind} SET name=?,{column}=?,active=? WHERE id=?', (name, extra, active, integer(data['id'], 'ID', 1)))
            else:
                db().execute(f'INSERT INTO {kind}(name,{column},active) VALUES(?,?,?)', (name, extra, active))
        return jsonify(ok=True)

    @app.post('/api/web/rules')
    @protected
    def add_rule():
        data = request.get_json()
        name = text(data.get('name'), 'Tên quy tắc')
        kind = data.get('kind')
        basis = data.get('basis')
        if kind not in ('percent', 'fixed') or basis not in ('before', 'after'):
            raise ValueError('Kiểu hoa hồng không hợp lệ.')
        try:
            raw = Decimal(str(data.get('value', '0')))
        except InvalidOperation:
            raise ValueError('Mức hoa hồng không hợp lệ.')
        if not raw.is_finite() or raw < 0 or (kind == 'percent' and raw > 100):
            raise ValueError('Hoa hồng phần trăm phải từ 0 đến 100%.')
        scaled = raw * 100 if kind == 'percent' else raw
        value = integer(scaled, 'Mức hoa hồng')
        starts = str(data.get('starts', ''))
        if datetime.strptime(starts, '%Y-%m-%d').strftime('%Y-%m-%d') != starts:
            raise ValueError('Ngày hiệu lực không hợp lệ.')
        employee = integer(data['employee_id'], 'Nhân viên', 1) if data.get('employee_id') else None
        service = integer(data['service_id'], 'Dịch vụ', 1) if data.get('service_id') else None
        with db():
            db().execute('BEGIN IMMEDIATE')
            if rows('SELECT id FROM web_commission_rules WHERE employee_id IS ? AND service_id IS ? AND starts=? AND active=1', (employee, service, starts)):
                raise ValueError('Đã có quy tắc cùng phạm vi và ngày hiệu lực. Hãy tắt quy tắc cũ trước.')
            db().execute('INSERT INTO web_commission_rules(name,employee_id,service_id,kind,value,basis,starts) VALUES(?,?,?,?,?,?,?)', (name, employee, service, kind, value, basis, starts))
        return jsonify(ok=True)

    @app.post('/api/web/rules/<int:rule_id>/toggle')
    @protected
    def toggle_rule(rule_id):
        with db():
            db().execute('BEGIN IMMEDIATE')
            rule = rows('SELECT * FROM web_commission_rules WHERE id=?', (rule_id,))
            if not rule:
                raise ValueError('Quy tắc không tồn tại.')
            r = rule[0]
            if not r['active'] and rows('SELECT id FROM web_commission_rules WHERE employee_id IS ? AND service_id IS ? AND starts=? AND active=1 AND id<>?', (r['employee_id'], r['service_id'], r['starts'],rule_id)):
                raise ValueError('Đã có quy tắc cùng phạm vi và ngày hiệu lực đang bật.')
            db().execute('UPDATE web_commission_rules SET active=1-active WHERE id=?', (rule_id,))
        return jsonify(ok=True)

    @app.post('/api/web/rules/<int:rule_id>/delete')
    @protected
    def delete_rule(rule_id):
        with db():
            deleted = db().execute('DELETE FROM web_commission_rules WHERE id=?', (rule_id,))
            if not deleted.rowcount:
                return jsonify(error='Mức hoa hồng không còn tồn tại.'), 404
        return jsonify(ok=True)

    def calculate(data):
        source = data.get('items')
        if not isinstance(source, list) or not 1 <= len(source) <= 50:
            raise ValueError('Đơn cần từ 1 đến 50 dòng dịch vụ.')
        result = []
        for item in source:
            service = rows('SELECT * FROM web_services WHERE id=? AND active=1', (integer(item.get('service_id'), 'Dịch vụ', 1),))
            employee = rows('SELECT * FROM web_employees WHERE id=? AND active=1', (integer(item.get('employee_id'), 'Nhân viên', 1),))
            if not service or not employee:
                raise ValueError('Dịch vụ hoặc nhân viên không còn hoạt động.')
            svc, emp = service[0], employee[0]
            svc['price'] = integer(svc['price'], 'Gia dich vu')
            quantity = integer(item.get('quantity'), 'Số lượng', 1, 100)
            result.append(dict(service_id=svc['id'], employee_id=emp['id'], service_name=svc['name'], employee_name=emp['name'], quantity=quantity, price=svc['price'], gross=svc['price'] * quantity))
        gross = sum(i['gross'] for i in result)
        discount = integer(data.get('discount', 0), 'Giảm giá', 0, gross)
        # Largest remainder allocation: line discounts always sum to the order discount.
        allocations = [discount * i['gross'] // gross if gross else 0 for i in result]
        remainders = sorted(range(len(result)), key=lambda n: discount * result[n]['gross'] % gross if gross else 0, reverse=True)
        for n in remainders[:discount - sum(allocations)]:
            allocations[n] += 1
        for i, allocated in zip(result, allocations):
            i['discount'] = allocated
            i['total'] = i['gross'] - allocated
            rules = rows('SELECT * FROM web_commission_rules WHERE active=1 AND starts<=? AND (employee_id IS NULL OR employee_id=?) AND (service_id IS NULL OR service_id=?) ORDER BY (CASE WHEN employee_id IS NOT NULL THEN 2 ELSE 0 END + CASE WHEN service_id IS NOT NULL THEN 1 ELSE 0 END) DESC, starts DESC,id DESC LIMIT 1', (today()[:10], i['employee_id'], i['service_id']))
            rule = rules[0] if rules else None
            i['rule_snapshot'] = DEFAULT_COMMISSION_SNAPSHOT
            i['commission'] = i['total']
            if rule:
                base = i['gross'] if rule['basis'] == 'before' else i['total']
                amount = Decimal(base) * rule['value'] / 10000 if rule['kind'] == 'percent' else Decimal(rule['value'] * i['quantity'])
                i['commission'] = int(amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                rate = f"{rule['value']/100:g}%" if rule['kind'] == 'percent' else f"{rule['value']:,}đ/lượt"
                i['rule_snapshot'] = f"{rule['name']} · {rate} · {'trước' if rule['basis']=='before' else 'sau'} giảm giá"
        return dict(items=result, gross=gross, discount=discount, total=gross-discount, commission=sum(i['commission'] for i in result))

    @app.post('/api/web/orders/preview')
    @protected
    def preview():
        return jsonify(calculate(request.get_json()))

    @app.post('/api/web/orders')
    @protected
    def create_order():
        data = request.get_json()
        key = text(data.get('request_key'), 'Mã yêu cầu', 100)
        payment = data.get('payment', 'unrecorded')
        if payment not in ('cash', 'transfer', 'unrecorded'):
            raise ValueError('Phương thức thanh toán không hợp lệ.')
        note = str(data.get('note', '')).strip()
        if len(note) > 500:
            raise ValueError('Ghi chú tối đa 500 ký tự.')
        with db():
            db().execute('BEGIN IMMEDIATE')
            existing = rows('SELECT id FROM web_orders WHERE request_key=?', (key,))
            if existing:
                return jsonify(id=existing[0]['id'], repeated=True)
            calculated = calculate(data)
            import hashlib, json
            fingerprint = hashlib.sha256(json.dumps(calculated, sort_keys=True).encode()).hexdigest()
            if data.get('quote') != fingerprint:
                return jsonify(error='Giá hoặc hoa hồng đã thay đổi. Hãy xem lại đơn rồi xác nhận.', quote=fingerprint, preview=calculated), 409
            employee_ids = {i['employee_id'] for i in calculated['items']}
            legacy_employee = next(iter(employee_ids)) if len(employee_ids) == 1 else None
            stamp = today()[:19].replace('T', ' ')
            cur = db().execute('INSERT INTO DonHang(NgayGio,NhanVienID,TongTien,created_at,updated_at) VALUES(?,?,?,?,?)', (stamp, legacy_employee, calculated['total'], stamp, stamp))
            order_id = cur.lastrowid
            db().execute('INSERT INTO web_order_meta(order_id,discount,commission,payment,note,status,request_key,created_by) VALUES(?,?,?,?,?,?,?,?)', (order_id, calculated['discount'], calculated['commission'], payment, note, 'paid', key, session['user']['id']))
            quantities = {}
            for line in calculated['items']:
                quantities[line['service_id']] = quantities.get(line['service_id'], 0) + line['quantity']
            for service_id, quantity in quantities.items():
                db().execute('INSERT INTO DonHang_DichVu(DonHangID,DichVuID,SoLuong,created_at,updated_at) VALUES(?,?,?,?,?)', (order_id, service_id, quantity, stamp, stamp))
            if legacy_employee:
                db().execute('UPDATE NhanVien SET ThuNhap=COALESCE(ThuNhap,0)+? WHERE ID=?', (calculated['total'], legacy_employee))
            for i in calculated['items']:
                db().execute('INSERT INTO web_order_items(order_id,service_id,employee_id,service_name,employee_name,quantity,price,discount,total,commission,rule_snapshot) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (order_id, i['service_id'], i['employee_id'], i['service_name'], i['employee_name'], i['quantity'], i['price'], i['discount'], i['total'], i['commission'], i['rule_snapshot']))
        return jsonify(id=order_id), 201

    @app.post('/api/web/orders/quote')
    @protected
    def quote():
        import hashlib, json
        calculated = calculate(request.get_json())
        return jsonify(preview=calculated, quote=hashlib.sha256(json.dumps(calculated, sort_keys=True).encode()).hexdigest())

    def month_range():
        month = request.args.get('month', today()[:7])
        try:
            start = datetime.strptime(month, '%Y-%m')
            if start.strftime('%Y-%m') != month:
                raise ValueError()
        except ValueError:
            raise ValueError('Tháng không hợp lệ.')
        end = f'{start.year+1}-01' if start.month == 12 else f'{start.year}-{start.month+1:02}'
        return month, end

    @app.get('/api/web/orders')
    @protected
    def get_orders():
        start, end = month_range()
        return jsonify(rows('SELECT * FROM web_orders WHERE created_at>=? AND created_at<? ORDER BY id DESC', (start, end)))

    @app.get('/api/web/orders/<int:order_id>')
    @protected
    def detail(order_id):
        order = rows('SELECT * FROM web_orders WHERE id=?', (order_id,))
        if not order:
            return jsonify(error='Không tìm thấy đơn.'), 404
        if order[0]['legacy']:
            legacy_items = rows('SELECT d.DichVuID service_id,s.Ten service_name,d.SoLuong quantity FROM DonHang_DichVu d LEFT JOIN DichVu s ON s.ID=d.DichVuID WHERE d.DonHangID=?', (order_id,))
            return jsonify(**order[0], items=legacy_items)
        return jsonify(**order[0], items=rows('SELECT * FROM web_order_items WHERE order_id=?', (order_id,)))

    @app.post('/api/web/orders/<int:order_id>/void')
    @protected
    def void(order_id):
        reason = text(request.get_json().get('reason'), 'Lý do hủy', 300)
        with db():
            db().execute('BEGIN IMMEDIATE')
            existing = rows('SELECT * FROM web_orders WHERE id=?', (order_id,))
            if not existing or existing[0]['status'] != 'paid':
                raise ValueError('Đơn không tồn tại hoặc đã hủy.')
            if existing[0]['legacy']:
                raise ValueError('Đơn WPF cũ cần đối soát trước khi hủy; chưa có snapshot hoa hồng.')
            db().execute("UPDATE web_order_meta SET status='void',voided_at=?,void_reason=? WHERE order_id=?", (today(), reason, order_id))
        return jsonify(ok=True)

    def report_data():
        start, end = month_range()
        period_month = start
        selected_day = request.args.get('day')
        if selected_day is not None:
            try:
                parsed = datetime.strptime(selected_day, '%Y-%m-%d')
                if parsed.strftime('%Y-%m-%d') != selected_day or selected_day[:7] != period_month:
                    raise ValueError()
            except ValueError:
                raise ValueError('Ngày báo cáo không hợp lệ hoặc không thuộc tháng đã chọn.')
            if request.args.get('group') == 'day':
                raise ValueError('Không kết hợp báo cáo tổng từng ngày với một ngày nhân viên riêng.')
            start, end = selected_day, (parsed + timedelta(days=1)).strftime('%Y-%m-%d')
        total = rows("SELECT COALESCE(SUM(total),0) revenue,COALESCE(SUM(commission),0) commission,COUNT(*) order_count,COALESCE(SUM(CASE WHEN payment='cash' THEN total ELSE 0 END),0) cash FROM web_orders WHERE created_at>=? AND created_at<?", (start, end))[0]
        reversal = rows('SELECT COALESCE(SUM(total),0) revenue,COALESCE(SUM(commission),0) commission FROM web_orders WHERE voided_at>=? AND voided_at<?', (start, end))[0]
        total['revenue'] -= reversal['revenue']
        total['commission'] -= reversal['commission']
        daily = rows("""
            SELECT day,SUM(revenue) revenue,SUM(quantity) quantity,SUM(commission) commission,
                   SUM(legacy_count) legacy_count,MAX(has_commission) has_commission FROM (
                SELECT substr(o.created_at,1,10) day,o.total revenue,
                       CASE WHEN o.legacy=1 THEN COALESCE((SELECT SUM(SoLuong) FROM DonHang_DichVu WHERE DonHangID=o.id),0)
                       ELSE COALESCE((SELECT SUM(quantity) FROM web_order_items WHERE order_id=o.id),0) END quantity,
                       COALESCE(o.commission,0) commission,o.legacy legacy_count,1 has_commission
                FROM web_orders o WHERE o.created_at>=? AND o.created_at<?
                UNION ALL
                SELECT substr(o.voided_at,1,10),-o.total,
                       -COALESCE((SELECT SUM(quantity) FROM web_order_items WHERE order_id=o.id),0),
                       -COALESCE(o.commission,0),0,1
                FROM web_orders o WHERE o.voided_at>=? AND o.voided_at<?
            ) GROUP BY day ORDER BY day
        """, (start,end,start,end))
        employees = rows("""
            SELECT employee_id,MAX(employee_name) employee_name,SUM(revenue) revenue,
                   SUM(commission) commission,SUM(quantity) quantity,
                   SUM(legacy_order_count) legacy_order_count,MAX(has_commission) has_commission
            FROM (
                SELECT i.employee_id,i.employee_name,i.total revenue,i.commission,i.quantity,
                       0 legacy_order_count,1 has_commission
                FROM web_order_items i JOIN web_orders o ON i.order_id=o.id
                WHERE o.legacy=0 AND o.created_at>=? AND o.created_at<?
                UNION ALL
                SELECT i.employee_id,i.employee_name,-i.total,-i.commission,-i.quantity,0,1
                FROM web_order_items i JOIN web_orders o ON i.order_id=o.id
                WHERE o.legacy=0 AND o.voided_at>=? AND o.voided_at<?
                UNION ALL
                SELECT d.NhanVienID,COALESCE(n.Ten,CASE WHEN d.NhanVienID IS NULL
                       THEN 'Chưa gán nhân viên' ELSE 'Nhân viên cũ #'||d.NhanVienID END),
                       o.total,o.commission,COALESCE((SELECT SUM(SoLuong) FROM DonHang_DichVu
                       WHERE DonHangID=d.ID),0),1,1
                FROM web_orders o JOIN DonHang d ON d.ID=o.id LEFT JOIN NhanVien n ON n.ID=d.NhanVienID
                WHERE o.legacy=1 AND o.created_at>=? AND o.created_at<?
            ) GROUP BY employee_id ORDER BY revenue DESC,employee_id
        """, (start,end,start,end,start,end))
        services = rows("""
            SELECT employee_id,service_id,service_name,
                   SUM(paid_quantity)-SUM(voided_quantity) quantity,
                   SUM(paid_quantity) paid_quantity,SUM(voided_quantity) voided_quantity,
                   SUM(completed_quantity) completed_quantity,
                   CASE WHEN SUM(missing_money)>0 THEN NULL ELSE MIN(price) END price_min,
                   CASE WHEN SUM(missing_money)>0 THEN NULL ELSE MAX(price) END price_max,
                   CASE WHEN SUM(missing_money)>0 THEN NULL ELSE SUM(completed_total) END total,
                   CASE WHEN SUM(missing_money)>0 THEN NULL ELSE SUM(completed_commission) END commission
            FROM (
                SELECT i.employee_id,i.service_id,i.service_name,i.quantity paid_quantity,0 voided_quantity,
                       CASE WHEN o.status='paid' THEN i.quantity ELSE 0 END completed_quantity,
                       CASE WHEN o.status='paid' THEN i.price END price,
                       CASE WHEN o.status='paid' THEN i.total ELSE 0 END completed_total,
                       CASE WHEN o.status='paid' THEN i.commission ELSE 0 END completed_commission,
                       0 missing_money
                FROM web_order_items i JOIN web_orders o ON i.order_id=o.id
                WHERE o.legacy=0 AND o.created_at>=? AND o.created_at<?
                UNION ALL
                SELECT i.employee_id,i.service_id,i.service_name,0,i.quantity,0,NULL,0,0,0
                FROM web_order_items i JOIN web_orders o ON i.order_id=o.id
                WHERE o.legacy=0 AND o.voided_at>=? AND o.voided_at<?
                UNION ALL
                SELECT d.NhanVienID,i.DichVuID,
                       COALESCE(s.Ten,'Dịch vụ cũ #'||i.DichVuID),COALESCE(i.SoLuong,0),0,COALESCE(i.SoLuong,0),
                       NULL,0,0,CASE WHEN COALESCE(i.SoLuong,0)>0 THEN 1 ELSE 0 END
                FROM web_orders o JOIN DonHang d ON d.ID=o.id
                JOIN DonHang_DichVu i ON i.DonHangID=d.ID LEFT JOIN DichVu s ON s.ID=i.DichVuID
                WHERE o.legacy=1 AND o.created_at>=? AND o.created_at<?
            ) GROUP BY employee_id,service_id,service_name COLLATE BINARY
            ORDER BY employee_id,paid_quantity DESC,service_name COLLATE BINARY,service_id
        """, (start,end,start,end,start,end))
        by_employee = {employee['employee_id']: employee for employee in employees}
        for employee in employees:
            employee['services'] = []
            employee['paid_quantity'] = employee['voided_quantity'] = employee['completed_quantity'] = 0
        for service in services:
            employee = by_employee[service.pop('employee_id')]
            employee['services'].append(service)
            employee['paid_quantity'] += service['paid_quantity']
            employee['voided_quantity'] += service['voided_quantity']
            employee['completed_quantity'] += service['completed_quantity']
        total['legacy_commission_rate'] = 100
        total['quantity'] = sum(e['quantity'] for e in employees)
        total['legacy_count'] = rows('SELECT COUNT(*) n FROM web_orders WHERE created_at>=? AND created_at<? AND legacy=1', (start,end))[0]['n']
        return dict(month=period_month, day=selected_day, totals=total, daily=daily, employees=employees)

    @app.get('/api/web/report')
    @protected
    def report():
        return jsonify(report_data())

    @app.get('/api/web/report.csv')
    @protected
    def export():
        data = report_data()
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        if request.args.get('group') == 'day':
            import calendar
            month = data['month'][:7]
            values = {row['day']: row for row in data['daily']}
            writer.writerow(['Ngày', 'Doanh thu (đ)', 'Lượt dịch vụ', 'Hoa hồng (đ)', 'Đơn cũ chưa lưu hoa hồng'])
            for day in range(1, calendar.monthrange(int(month[:4]), int(month[5:]))[1] + 1):
                stamp = f'{month}-{day:02d}'
                row = values.get(stamp)
                if row:
                    writer.writerow([stamp, row['revenue'], row['quantity'], row['commission'] if row['has_commission'] else '', row['legacy_count']])
                else:
                    writer.writerow([stamp] + ([0,0,0,0] if stamp <= today()[:10] else ['','','','']))
            writer.writerow(['Tổng tháng', data['totals']['revenue'], data['totals']['quantity'], data['totals']['commission'], data['totals']['legacy_count']])
        else:
            writer.writerow(['Nhân viên', 'Doanh thu nhân viên (đ)', 'Hoa hồng (đ)', 'Lượt dịch vụ', 'Đơn cũ chưa lưu hoa hồng'])
            for row in data['employees']:
                name = row['employee_name']
                if name.startswith(('=', '+', '-', '@', '\t', '\r')):
                    name = "'" + name
                writer.writerow([name, row['revenue'], row['commission'] if row['has_commission'] else '', row['quantity'], row['legacy_order_count']])
            writer.writerow(['Tổng ngày' if data['day'] else 'Tổng', data['totals']['revenue'], data['totals']['commission'], data['totals']['quantity'], data['totals']['legacy_count']])
        return app.response_class('\ufeff' + output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="BlockHouse-{data["day"] or data["month"]}.csv"'})

    return app



