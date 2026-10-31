import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app import create_app
from web_api import today
from flask.testing import FlaskClient


class TokenClient(FlaskClient):
    def open(self, *args, **kwargs):
        args = list(args)
        if args and isinstance(args[0], str):
            args[0] = args[0].replace('/api/', '/api/web/', 1)
        headers = dict(kwargs.pop('headers', {}))
        if getattr(self, 'token', None):
            headers['Authorization'] = 'Bearer ' + self.token
        response = super().open(*args, headers=headers, **kwargs)
        if response.is_json and isinstance(response.json, dict) and response.json.get('token'):
            self.token = response.json['token']
        return response



class BlockHouseTest(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parent.parent / 'data'
        test_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(self.path), 'WEB_ALLOWED_ORIGINS': ['http://127.0.0.1:8080']})
        self.app.test_client_class = TokenClient
        self.client = self.app.test_client()
        self.csrf = self.client.get('/api/session').json['csrf']
        response = self.post('/api/setup', {'name': 'owner', 'password': 'strong-test-password'})
        self.assertEqual(response.status_code, 200)
        self.csrf = response.json['csrf']
        self.post('/api/catalog/employees', {'name': 'Thợ A'})
        self.post('/api/catalog/employees', {'name': 'Thợ B'})
        self.post('/api/catalog/services', {'name': 'Cắt tóc', 'price': 100000})
        self.post('/api/catalog/services', {'name': 'Gội đầu', 'price': 50000})

    def tearDown(self):
        from models import db
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp.cleanup()

    def post(self, path, body):
        return self.client.post(path, json=body, headers={'X-CSRF-Token': self.csrf})

    def rule(self, **kwargs):
        data = dict(name='Mặc định', kind='percent', value=40, basis='after', starts='2020-01-01')
        data.update(kwargs)
        return self.post('/api/rules', data)

    def payload(self):
        return dict(items=[dict(service_id=1, employee_id=1, quantity=1), dict(service_id=2, employee_id=2, quantity=1)], discount=15000, payment='cash', request_key='request-1')

    def save(self, data):
        quote = self.post('/api/orders/quote', data)
        self.assertEqual(quote.status_code, 200)
        return self.post('/api/orders', dict(data, quote=quote.json['quote']))

    def test_order_without_discount_or_payment_uses_full_price_and_untracked_method(self):
        self.rule()
        data = self.payload()
        data.pop('discount')
        data.pop('payment')
        preview = self.post('/api/orders/quote', data).json['preview']
        self.assertEqual(preview['gross'], 150000)
        self.assertEqual(preview['total'], 150000)
        self.assertEqual(preview['discount'], 0)
        self.assertEqual(preview['commission'], 60000)
        response = self.save(data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.save(data).json['id'], response.json['id'])
        detail = self.client.get('/api/orders/'+str(response.json['id'])).json
        self.assertEqual(detail['payment'], 'unrecorded')
        self.assertEqual(detail['discount'], 0)
        self.assertTrue(all(item['discount'] == 0 for item in detail['items']))
        report = self.client.get('/api/report').json
        self.assertEqual(report['totals']['revenue'], 150000)
        self.assertEqual(report['totals']['commission'], 60000)
        self.assertEqual(report['totals']['cash'], 0)
        invalid = dict(data,payment='invalid',request_key='invalid-payment')
        self.assertEqual(self.save(invalid).status_code,400)

    def test_commission_discount_snapshots_idempotency_and_void(self):
        self.assertEqual(self.rule().status_code, 200)
        self.assertEqual(self.rule(name='Gội cố định', service_id=2, kind='fixed', value=15000).status_code, 200)
        data = self.payload()
        preview = self.post('/api/orders/quote', data).json['preview']
        self.assertEqual(preview['total'], 135000)
        self.assertEqual(preview['commission'], 51000)
        self.assertEqual([i['discount'] for i in preview['items']], [10000, 5000])
        response = self.save(data)
        self.assertEqual(response.status_code, 201)
        order_id = response.json['id']
        self.assertEqual(self.save(data).json['id'], order_id)
        self.post('/api/catalog/services', dict(id=1, name='Cắt mới', price=200000))
        self.rule(name='Mức mới', value=90, starts=today()[:10])
        detail = self.client.get(f'/api/orders/{order_id}').json
        self.assertEqual(detail['items'][0]['price'], 100000)
        self.assertEqual(detail['commission'], 51000)
        self.assertEqual(self.client.get('/api/report').json['totals']['revenue'], 135000)
        response = self.post(f'/api/orders/{order_id}/void', {'reason': 'Khách yêu cầu hoàn'})
        self.assertEqual(response.status_code, 200)
        totals = self.client.get('/api/report').json['totals']
        self.assertEqual(totals['revenue'], 0)
        self.assertEqual(totals['commission'], 0)
        self.assertEqual(self.post(f'/api/orders/{order_id}/void', {'reason': 'Lặp'}).status_code, 400)
        self.assertEqual(self.client.get(f'/api/orders/{order_id}').json['status'], 'void')

    def test_quote_detects_price_change_and_no_partial_order(self):
        data = self.payload()
        data['quote'] = self.post('/api/orders/quote', data).json['quote']
        self.post('/api/catalog/services', dict(id=1, name='Cắt', price=110000))
        response = self.post('/api/orders', data)
        self.assertEqual(response.status_code, 409)
        self.assertIn('quote', response.json)
        self.assertEqual(self.client.get('/api/orders').json, [])
        data['quote'] = response.json['quote']
        self.assertEqual(self.post('/api/orders', data).status_code, 201)

    def test_rounding_and_rule_priority(self):
        self.rule()
        self.rule(name='Dịch vụ', service_id=1, value=20)
        self.rule(name='Nhân viên', employee_id=1, value=30)
        self.rule(name='Cụ thể', employee_id=1, service_id=1, value=50)
        data = self.payload()
        data['discount'] = 1
        p = self.post('/api/orders/quote', data).json['preview']
        self.assertEqual(sum(i['discount'] for i in p['items']), 1)
        self.assertEqual(p['items'][0]['commission'], 50000)
        self.assertIn('Cụ thể', p['items'][0]['rule_snapshot'])

    def test_validation_and_csrf(self):
        self.assertEqual(self.client.post('/api/orders', json={}).status_code, 403)
        self.assertEqual(self.rule(value=101).status_code, 400)
        self.assertEqual(self.rule(value='abc').status_code, 400)
        self.assertEqual(self.rule(value='NaN').status_code, 400)
        data = self.payload()
        data['items'][0]['quantity'] = -1
        self.assertEqual(self.post('/api/orders/quote', data).status_code, 400)
        data = self.payload()
        data['discount'] = 200000
        self.assertEqual(self.post('/api/orders/quote', data).status_code, 400)
        self.assertEqual(self.client.get('/api/report?month=2026-99').status_code, 400)
        self.assertEqual(self.post('/api/orders/quote', []).status_code, 400)

    def test_catalog_inactive_and_rule_collision(self):
        self.rule()
        self.assertEqual(self.rule().status_code, 400)
        self.post('/api/catalog/employees', dict(id=1, name='A', active=0))
        self.assertEqual(self.post('/api/orders/quote', self.payload()).status_code, 400)
        self.assertEqual(self.client.get('/api/orders').json, [])

    def test_auth_and_export(self):
        self.rule()
        self.save(self.payload())
        exported = self.client.get('/api/report.csv')
        self.assertEqual(exported.status_code, 200)
        self.assertIn('135000', exported.get_data(as_text=True))
        self.post('/api/logout', {})
        self.assertEqual(self.client.get('/api/catalog').status_code, 401)
        self.assertEqual(self.client.get('/api/report.csv').status_code, 401)
        self.csrf = self.client.get('/api/session').json['csrf']
        login = self.post('/api/login', dict(name='owner', password='strong-test-password'))
        self.assertEqual(login.status_code, 200)

    def test_reversal_recorded_in_month_of_void(self):
        self.rule()
        self.save(self.payload())
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE DonHang SET NgayGio='2020-12-31 23:00:00'")
        self.post('/api/orders/1/void', {'reason': 'Hoàn khác kỳ'})
        past = self.client.get('/api/report?month=2020-12').json
        current = self.client.get('/api/report').json
        self.assertEqual(past['totals']['revenue'], 135000)
        self.assertEqual(current['totals']['revenue'], -135000)
        self.assertEqual(sum(e['commission'] for e in current['employees']), -54000)
        for report in (past, current):
            for field in ('revenue','quantity','commission'):
                self.assertEqual(sum(row[field] for row in report['daily']), report['totals'][field])


    def test_browser_origin_host_preflight_and_revocation(self):
        headers = {'Origin':'http://127.0.0.1:8080', 'Access-Control-Request-Method':'POST', 'Access-Control-Request-Headers':'authorization,content-type,x-csrf-token'}
        response = self.client.options('/api/orders', headers=headers)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], headers['Origin'])
        self.assertNotIn('Access-Control-Allow-Credentials', response.headers)
        denied = self.client.get('/api/catalog', headers={'Origin':'https://untrusted.example'})
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn('Access-Control-Allow-Origin', denied.headers)
        rebound = self.client.get('/api/session', base_url='http://untrusted.example')
        self.assertEqual(rebound.status_code, 403)
        token = self.client.token
        self.post('/api/logout', {})
        raw = FlaskClient(self.app)
        self.assertEqual(raw.get('/api/web/catalog', headers={'Authorization':'Bearer '+token}).status_code, 401)
        self.assertEqual(raw.get('/api/v1/health').status_code, 200)

    def test_legacy_commission_defaults_to_full_stored_total(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            stamp = today()[:19].replace('T', ' ')
            connection.execute('INSERT INTO DonHang(ID,NgayGio,NhanVienID,TongTien) VALUES(100,?,1,123000)', (stamp,))
            connection.execute('INSERT INTO DonHang_DichVu(DonHangID,DichVuID,SoLuong) VALUES(100,1,1)')
        order = self.client.get('/api/orders/100').json
        self.assertTrue(order['legacy'])
        self.assertEqual(order['total'], 123000)
        self.assertEqual(order['commission'], 123000)
        self.assertNotIn('price', order['items'][0])
        self.rule(value=20)
        self.assertEqual(self.client.get('/api/orders/100').json['commission'], 123000)
        self.post('/api/catalog/services', {'id':1,'name':'New price','price':999000})
        self.assertEqual(self.client.get('/api/report').json['totals']['revenue'], 123000)
        self.assertEqual(self.client.get('/api/report').json['totals']['legacy_count'], 1)
        report = self.client.get('/api/report').json
        employee = report['employees'][0]
        self.assertEqual(employee['employee_id'], 1)
        self.assertEqual(employee['revenue'], 123000)
        self.assertEqual(employee['quantity'], 1)
        self.assertEqual(employee['legacy_order_count'], 1)
        self.assertTrue(employee['has_commission'])
        self.assertEqual(employee['commission'], 123000)
        self.assertEqual(report['daily'][0]['quantity'], 1)
        self.assertTrue(report['daily'][0]['has_commission'])
        self.assertEqual(report['totals']['commission'], 123000)
        self.assertEqual(report['daily'][0]['legacy_count'], 1)
        self.assertEqual(sum(row['revenue'] for row in report['daily']), 123000)
        self.assertIn('123000', self.client.get('/api/report.csv?group=day').get_data(as_text=True))
        self.assertEqual(self.post('/api/orders/100/void', {'reason':'Needs reconciliation'}).status_code, 400)

    def test_import_upgrade_defaults_only_legacy_commissions_and_is_repeatable(self):
        from runtime import import_database
        from models import db
        self.save(self.payload())  # A recorded zero is a known commission, not legacy.
        self.rule()
        data = dict(self.payload(), request_key='second-order')
        self.save(data)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("INSERT INTO DonHang(ID,NgayGio,NhanVienID,TongTien) VALUES(100,'2020-01-01 10:00:00',1,123000)")
            connection.execute('DROP VIEW web_orders')
            connection.execute('CREATE VIEW web_orders AS SELECT ID id,NULL commission FROM DonHang')
        source_before = self.path.read_bytes()
        installed = Path(self.temp.name) / 'installed.db'
        import_database(self.path, installed)
        for _ in range(2):
            upgraded = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(installed)})
            with upgraded.app_context():
                db.session.remove()
                db.engine.dispose()
            with closing(sqlite3.connect(installed)) as connection:
                self.assertEqual(connection.execute('SELECT commission FROM web_orders ORDER BY id').fetchall(), [(0,), (54000,), (123000,)])
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM DonHang').fetchone()[0], 3)
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM web_order_meta').fetchone()[0], 2)
        self.assertEqual(self.path.read_bytes(), source_before)

    def test_mixed_legacy_revenue_counts_each_order_once(self):
        self.rule()
        self.save(self.payload())
        with closing(sqlite3.connect(self.path)) as connection, connection:
            stamp = today()[:19].replace('T', ' ')
            connection.execute('INSERT INTO DonHang(ID,NgayGio,NhanVienID,TongTien) VALUES(100,?,1,123000)', (stamp,))
            connection.executemany('INSERT INTO DonHang_DichVu(DonHangID,DichVuID,SoLuong) VALUES(100,?,?)', [(1,2),(2,3)])
            connection.execute('INSERT INTO DonHang(ID,NgayGio,NhanVienID,TongTien) VALUES(101,?,NULL,45000)', (stamp,))
        report = self.client.get('/api/report').json
        self.assertEqual(sum(row['revenue'] for row in report['employees']), report['totals']['revenue'])
        employee = next(row for row in report['employees'] if row['employee_id'] == 1)
        self.assertEqual(employee['revenue'], 213000)
        self.assertEqual(employee['quantity'], 6)
        self.assertEqual(employee['commission'], 159000)
        self.assertTrue(employee['has_commission'])
        self.assertEqual(employee['legacy_order_count'], 1)
        for field in ('revenue','quantity','commission'):
            self.assertEqual(sum(row[field] for row in report['daily']), report['totals'][field])
        self.assertIn('Lượt dịch vụ', self.client.get('/api/report.csv?group=day').get_data(as_text=True))
        self.assertEqual(next(row for row in report['employees'] if row['employee_id'] is None)['revenue'], 45000)

    def test_employee_day_report_includes_legacy_and_reversals_on_their_days(self):
        self.rule()
        self.save(self.payload())
        self.assertEqual(self.post('/api/orders/1/void', {'reason':'Hoàn ngày sau'}).status_code, 200)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE DonHang SET NgayGio='2020-12-01 10:00:00' WHERE ID=1")
            connection.execute("UPDATE web_order_meta SET voided_at='2020-12-02T10:00:00+07:00' WHERE order_id=1")
            connection.execute("INSERT INTO DonHang(ID,NgayGio,NhanVienID,TongTien) VALUES(100,'2020-12-02 11:00:00',1,123000)")
            connection.execute('INSERT INTO DonHang_DichVu(DonHangID,DichVuID,SoLuong) VALUES(100,1,3)')
            connection.execute("INSERT INTO DonHang(ID,NgayGio,NhanVienID,TongTien) VALUES(101,'2020-12-03 10:00:00',2,999)")
        first = self.client.get('/api/report?month=2020-12&day=2020-12-01').json
        second = self.client.get('/api/report?month=2020-12&day=2020-12-02').json
        legacy = self.client.get('/api/report?month=2020-12&day=2020-12-03').json
        self.assertEqual(first['month'], '2020-12')
        self.assertEqual(first['day'], '2020-12-01')
        self.assertEqual(first['totals']['revenue'], 135000)
        self.assertEqual(first['totals']['quantity'], 2)
        self.assertEqual(first['totals']['commission'], 54000)
        self.assertEqual(second['totals']['revenue'], -12000)
        self.assertEqual(second['totals']['quantity'], 1)
        self.assertEqual(second['totals']['commission'], 69000)
        employee = next(row for row in second['employees'] if row['employee_id'] == 1)
        self.assertEqual(employee['revenue'], 33000)
        self.assertEqual(employee['legacy_order_count'], 1)
        self.assertTrue(legacy['employees'][0]['has_commission'])
        self.assertEqual(legacy['employees'][0]['commission'], 999)
        for report in (first,second,legacy):
            for field in ('revenue','quantity','commission'):
                self.assertEqual(sum(row[field] for row in report['employees']), report['totals'][field])
        exported = self.client.get('/api/report.csv?month=2020-12&day=2020-12-02')
        self.assertIn('Tổng ngày,-12000,69000,1,1', exported.get_data(as_text=True))
        self.assertIn('2020-12-02.csv', exported.headers['Content-Disposition'])
        empty = self.client.get('/api/report?month=2020-12&day=2020-12-04').json
        self.assertEqual(empty['employees'], [])
        self.assertEqual(empty['totals']['revenue'], 0)
        for day in ('2020-12-32','2020-11-30','20201201',''):
            self.assertEqual(self.client.get('/api/report?month=2020-12&day='+day).status_code, 400)
        self.assertEqual(self.client.get('/api/report?month=2020-12&day=2020-12-01&group=day').status_code,400)

    def test_expired_token_is_rejected(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute('UPDATE web_sessions SET expires=0')
        self.assertEqual(self.client.get('/api/catalog').status_code, 401)

    def test_legacy_data_endpoints_are_disabled_even_without_origin(self):
        raw = FlaskClient(self.app)
        for path, method in [('/api/v1/services/', 'GET'), ('/api/v1/orders/', 'POST'), ('/api/v1/employees/', 'POST')]:
            self.assertEqual(raw.open(path, method=method, json={}).status_code, 410)
        self.assertEqual(raw.get('/api/web/health').json, {'app': 'BlockHouse', 'api_version': 2})

    def test_password_change_revokes_other_tokens_and_requires_current_password(self):
        raw = FlaskClient(self.app)
        old = self.client.token
        self.assertEqual(self.post('/api/account/password', {'current_password': 'wrong', 'new_password': 'another-strong-password'}).status_code, 400)
        self.assertEqual(self.post('/api/account/password', {'current_password': 'strong-test-password', 'new_password': 'short'}).status_code, 400)
        result = self.post('/api/account/password', {'current_password': 'strong-test-password', 'new_password': 'another-strong-password'})
        self.assertEqual(result.status_code, 200)
        self.csrf = result.json['csrf']
        self.assertNotEqual(result.json['token'], old)
        self.assertEqual(raw.get('/api/web/catalog', headers={'Authorization': 'Bearer ' + old}).status_code, 401)
        self.assertEqual(self.client.get('/api/catalog').status_code, 200)
        self.assertEqual(self.post('/api/login', {'name': 'owner', 'password': 'strong-test-password'}).status_code, 401)
        self.assertEqual(self.post('/api/login', {'name': 'owner', 'password': 'another-strong-password'}).status_code, 200)

    def test_new_password_preserves_intentional_spaces(self):
        password = '  another strong password  '
        response = self.post('/api/account/password', {'current_password': 'strong-test-password', 'new_password': password})
        self.assertEqual(response.status_code, 200)
        self.csrf = response.json['csrf']
        self.assertEqual(self.post('/api/login', {'name': 'owner', 'password': password}).status_code, 200)

    def test_password_attempts_are_limited(self):
        for _ in range(10):
            self.assertEqual(self.post('/api/account/password', {'current_password': 'wrong', 'new_password': 'another-strong-password'}).status_code, 400)
        self.assertEqual(self.post('/api/account/password', {'current_password': 'wrong', 'new_password': 'another-strong-password'}).status_code, 429)

    def test_backup_is_authenticated_and_matches_database(self):
        raw = FlaskClient(self.app)
        self.assertEqual(raw.get('/api/web/maintenance').status_code, 401)
        result = self.post('/api/maintenance/backup', {})
        self.assertEqual(result.status_code, 200)
        backup = Path(result.json['backup']['folder']) / result.json['filename']
        with closing(sqlite3.connect(backup)) as connection:
            self.assertEqual(connection.execute('PRAGMA quick_check').fetchone()[0], 'ok')
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM NhanVien').fetchone()[0], 2)
        self.assertEqual(raw.post('/api/web/maintenance/backup', json={}).status_code, 403)

    def test_desktop_origin_is_allowed_but_does_not_bypass_auth(self):
        raw = FlaskClient(self.app)
        response = raw.get('/api/web/catalog', headers={'Origin': 'https://blockhouse.desktop'})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'https://blockhouse.desktop')


if __name__ == '__main__':
    unittest.main()


