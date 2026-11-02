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
        self.rule(name='Intentional zero', value=0)
        zero = self.client.get('/api/catalog').json['rules'][0]['id']
        self.save(self.payload())  # Explicit 0% is a known commission, not legacy.
        self.post(f'/api/rules/{zero}/toggle', {})
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

    def test_employee_service_breakdown_keeps_snapshots_and_legacy_quantities(self):
        self.rule()
        self.save(dict(items=[dict(service_id=1, employee_id=1, quantity=2),
                              dict(service_id=2, employee_id=1, quantity=1),
                              dict(service_id=1, employee_id=2, quantity=1)], request_key='original-services'))
        self.post('/api/catalog/services', dict(id=1, name='Cat toc', price=999000))
        self.post('/api/catalog/services', dict(name='Cắt tóc', price=1))
        self.save(dict(items=[dict(service_id=1, employee_id=1, quantity=1),
                              dict(service_id=3, employee_id=1, quantity=2)], request_key='renamed-services'))
        with closing(sqlite3.connect(self.path)) as connection, connection:
            stamp = today()[:19].replace('T', ' ')
            connection.execute('INSERT INTO DonHang(ID,NgayGio,NhanVienID,TongTien) VALUES(100,?,1,123000)', (stamp,))
            connection.executemany('INSERT INTO DonHang_DichVu(DonHangID,DichVuID,SoLuong) VALUES(100,?,?)', [(1,3),(2,2)])
        report = self.client.get('/api/report').json
        employee = next(row for row in report['employees'] if row['employee_id'] == 1)
        services = {(row['service_id'], row['service_name']): row for row in employee['services']}
        self.assertEqual({key: row['quantity'] for key,row in services.items()},
                         {(1,'Cắt tóc'):2, (1,'Cat toc'):4, (2,'Gội đầu'):3, (3,'Cắt tóc'):2})
        self.assertEqual(employee['quantity'], 11)
        self.assertEqual(employee['completed_quantity'], 11)
        self.assertEqual(employee['paid_quantity'], 11)
        self.assertEqual(employee['voided_quantity'], 0)
        self.assertEqual(employee['revenue'], 1372002)
        self.assertEqual(self.client.get('/api/orders/1').json['items'][0]['price'], 100000)
        second = next(row for row in report['employees'] if row['employee_id'] == 2)
        self.assertEqual([(row['service_id'],row['quantity']) for row in second['services']], [(1,1)])
        daily = self.client.get('/api/report?month='+today()[:7]+'&day='+today()[:10]).json
        self.assertEqual(daily['employees'], report['employees'])
        for row in report['employees']:
            self.assertEqual(sum(service['quantity'] for service in row['services']), row['quantity'])
            self.assertEqual(sum(service['paid_quantity'] for service in row['services']), row['paid_quantity'])
            self.assertEqual(sum(service['voided_quantity'] for service in row['services']), row['voided_quantity'])
            self.assertEqual(sum(service['completed_quantity'] for service in row['services']), row['completed_quantity'])

    def test_employee_service_breakdown_separates_same_day_and_later_voids(self):
        self.rule()
        previous = self.save(dict(items=[dict(service_id=1,employee_id=1,quantity=2),
                                         dict(service_id=2,employee_id=1,quantity=3)],request_key='previous-day')).json['id']
        kept = self.save(dict(items=[dict(service_id=1,employee_id=1,quantity=4)],request_key='kept')).json['id']
        canceled = self.save(dict(items=[dict(service_id=1,employee_id=1,quantity=5)],request_key='same-day-void')).json['id']
        self.assertEqual(self.post(f'/api/orders/{previous}/void', {'reason':'Hoàn ngày sau'}).status_code, 200)
        self.assertEqual(self.post(f'/api/orders/{canceled}/void', {'reason':'Hoàn cùng ngày'}).status_code, 200)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE DonHang SET NgayGio='2020-12-01 10:00:00' WHERE ID=?", (previous,))
            connection.execute("UPDATE DonHang SET NgayGio='2020-12-02 10:00:00' WHERE ID IN (?,?)", (kept,canceled))
            connection.execute("UPDATE web_order_meta SET voided_at='2020-12-03T10:00:00+07:00' WHERE order_id=?", (previous,))
            connection.execute("UPDATE web_order_meta SET voided_at='2020-12-02T11:00:00+07:00' WHERE order_id=?", (canceled,))
        for day,expected in [('2020-12-01',(5,0,5)),('2020-12-02',(9,5,4)),('2020-12-03',(0,5,-5)),(None,(14,10,4))]:
            query = '/api/report?month=2020-12' + ('&day='+day if day else '')
            report = self.client.get(query).json
            employee = report['employees'][0]
            self.assertEqual((employee['paid_quantity'],employee['voided_quantity'],employee['quantity']),expected)
            for field in ('quantity','paid_quantity','voided_quantity'):
                self.assertEqual(sum(service[field] for service in employee['services']),employee[field])
            for service in employee['services']:
                self.assertEqual(service['quantity'],service['paid_quantity']-service['voided_quantity'])
            self.assertEqual(employee['quantity'],report['totals']['quantity'])
        reversal = self.client.get('/api/report?month=2020-12&day=2020-12-03').json['employees'][0]
        self.assertEqual({row['service_id']:row['quantity'] for row in reversal['services']},{1:-2,2:-3})
        empty = self.client.get('/api/report?month=2020-12&day=2020-12-04').json
        self.assertEqual(empty['employees'],[])

    def test_employee_service_breakdown_retains_missing_and_inactive_legacy_services(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            stamp = today()[:19].replace('T', ' ')
            connection.execute('INSERT INTO DonHang(ID,NgayGio,NhanVienID,TongTien) VALUES(100,?,NULL,123000)', (stamp,))
            connection.execute('INSERT INTO DonHang_DichVu(DonHangID,DichVuID,SoLuong) VALUES(100,999,4)')
            connection.execute('INSERT INTO DonHang(ID,NgayGio,NhanVienID,TongTien) VALUES(101,?,1,50000)', (stamp,))
            connection.execute('INSERT INTO DonHang_DichVu(DonHangID,DichVuID,SoLuong) VALUES(101,1,2)')
            connection.execute('UPDATE web_service_state SET active=0 WHERE service_id=1')
        report = self.client.get('/api/report').json
        unknown = next(row for row in report['employees'] if row['employee_id'] is None)
        self.assertEqual(unknown['services'],[dict(service_id=999,service_name='Dịch vụ cũ #999',quantity=4,paid_quantity=4,voided_quantity=0,completed_quantity=4,price_min=None,price_max=None,total=None,commission=None)])
        known = next(row for row in report['employees'] if row['employee_id'] == 1)
        self.assertEqual(known['services'][0]['quantity'],2)
        self.assertEqual(known['services'][0]['service_name'],'Cắt tóc')
        self.assertEqual(sum(row['quantity'] for row in report['employees']),report['totals']['quantity'])

    def test_completed_service_quantity_counts_creation_day_without_financial_reversals(self):
        self.rule()
        previous = self.save(dict(items=[dict(service_id=1,employee_id=1,quantity=6)],request_key='previous-six')).json['id']
        kept = self.save(dict(items=[dict(service_id=1,employee_id=1,quantity=5)],request_key='completed-five')).json['id']
        canceled = self.save(dict(items=[dict(service_id=1,employee_id=1,quantity=3)],request_key='canceled-three')).json['id']
        self.assertEqual(self.post(f'/api/orders/{previous}/void', {'reason':'Hủy đơn ngày trước'}).status_code,200)
        self.assertEqual(self.post(f'/api/orders/{canceled}/void', {'reason':'Hủy đơn cùng ngày'}).status_code,200)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE DonHang SET NgayGio='2020-12-01 10:00:00' WHERE ID=?", (previous,))
            connection.execute("UPDATE DonHang SET NgayGio='2020-12-02 10:00:00' WHERE ID IN (?,?)", (kept,canceled))
            connection.execute("UPDATE web_order_meta SET voided_at='2020-12-02T11:00:00+07:00' WHERE order_id IN (?,?)", (previous,canceled))
        report = self.client.get('/api/report?month=2020-12&day=2020-12-02').json
        employee = report['employees'][0]
        self.assertEqual(employee['completed_quantity'],5)
        self.assertEqual(employee['quantity'],-1)
        self.assertEqual(employee['paid_quantity'],8)
        self.assertEqual(employee['voided_quantity'],9)
        self.assertEqual(employee['services'][0]['completed_quantity'],5)
        self.assertEqual(employee['services'][0]['quantity'],-1)
        self.assertEqual(report['totals']['quantity'],-1)
        self.assertEqual(report['totals']['revenue'],-100000)
        previous_report = self.client.get('/api/report?month=2020-12&day=2020-12-01').json
        self.assertEqual(previous_report['employees'][0]['completed_quantity'],0)
        self.assertEqual(previous_report['employees'][0]['services'][0]['completed_quantity'],0)
        self.assertEqual(previous_report['totals']['quantity'],6)
        monthly = self.client.get('/api/report?month=2020-12').json
        self.assertEqual(monthly['employees'][0]['completed_quantity'],5)
        self.assertEqual(monthly['employees'][0]['quantity'],5)

    def test_employee_service_money_uses_paid_snapshots_and_marks_legacy_unknown(self):
        self.rule()
        first = self.save(dict(items=[dict(service_id=1,employee_id=1,quantity=2)],discount=10000,request_key='price-one')).json['id']
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute('UPDATE DichVu SET Gia=120000 WHERE ID=1')
        second = self.save(dict(items=[dict(service_id=1,employee_id=1,quantity=1)],request_key='price-two')).json['id']
        canceled = self.save(dict(items=[dict(service_id=1,employee_id=1,quantity=4)],request_key='price-cancel')).json['id']
        self.post(f'/api/orders/{canceled}/void', {'reason':'Canceled'})
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute('UPDATE DichVu SET Gia=999999 WHERE ID=1')
        report = self.client.get('/api/report').json
        service = report['employees'][0]['services'][0]
        self.assertEqual(service['completed_quantity'],3)
        self.assertEqual((service['price_min'],service['price_max']),(100000,120000))
        self.assertEqual(service['total'],310000)
        self.assertEqual(service['commission'],124000)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute('INSERT INTO DonHang(ID,NgayGio,NhanVienID,TongTien) VALUES(100000,?,1,80000)',(today()[:19].replace('T',' '),))
            connection.execute('INSERT INTO DonHang_DichVu(DonHangID,DichVuID,SoLuong) VALUES(100000,1,1)')
        mixed = self.client.get('/api/report').json['employees'][0]['services'][0]
        self.assertEqual(mixed['completed_quantity'],4)
        for field in ('price_min','price_max','total','commission'):
            self.assertIsNone(mixed[field])

    def test_missing_commission_defaults_to_full_net_total_and_respects_explicit_zero(self):
        self.rule(name='Future rule', value=25, starts='2999-01-01')
        data = self.payload()
        preview = self.post('/api/orders/quote', data).json['preview']
        self.assertEqual(preview['commission'], 135000)
        self.assertEqual([i['commission'] for i in preview['items']], [90000,45000])
        self.assertTrue(all(i['rule_snapshot'] == 'Mặc định · 100% · sau giảm giá' for i in preview['items']))
        self.rule(name='Explicit zero', employee_id=2, value=0)
        preview = self.post('/api/orders/quote', data).json['preview']
        self.assertEqual(preview['commission'], 90000)
        self.assertEqual(preview['items'][1]['commission'], 0)
        order_id = self.save(data).json['id']
        self.assertEqual(self.client.get(f'/api/orders/{order_id}').json['commission'], 90000)
        report = self.client.get('/api/report').json
        employees = {row['employee_id']: row for row in report['employees']}
        self.assertEqual(employees[1]['services'][0]['commission'], 90000)
        self.assertEqual(employees[2]['services'][0]['commission'], 0)

    def test_startup_corrects_only_old_missing_rule_snapshots_with_backup_and_is_repeatable(self):
        from models import db
        self.rule(name='Explicit zero', employee_id=2, value=0)
        old = self.save(self.payload()).json['id']
        self.rule(name='Recorded 40 percent', employee_id=1, value=40)
        recorded = self.save(dict(self.payload(), request_key='recorded')).json['id']
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE web_order_items SET commission=0,rule_snapshot='Chưa cấu hình · 0đ' WHERE order_id=? AND employee_id=1", (old,))
            connection.execute('UPDATE web_order_meta SET commission=0 WHERE order_id=?', (old,))
            before = connection.execute('SELECT id,order_id,quantity,price,discount,total FROM web_order_items ORDER BY id').fetchall()
        for _ in range(2):
            upgraded = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(self.path)})
            with upgraded.app_context():
                db.session.remove()
                db.engine.dispose()
        backups = list(self.path.parent.glob(self.path.name + '.before-default-commission-100-*.bak'))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as backup:
            self.assertEqual(backup.execute('PRAGMA quick_check').fetchone()[0], 'ok')
            self.assertEqual(backup.execute('SELECT commission FROM web_order_meta WHERE order_id=?', (old,)).fetchone()[0], 0)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute('SELECT id,order_id,quantity,price,discount,total FROM web_order_items ORDER BY id').fetchall(), before)
        self.assertEqual(self.client.get(f'/api/orders/{old}').json['commission'], 90000)
        self.assertEqual(self.client.get(f'/api/orders/{recorded}').json['commission'], 36000)
        self.assertEqual(self.client.get(f'/api/orders/{old}').json['items'][1]['commission'], 0)
        for query in ('/api/report', '/api/report?month=' + today()[:7] + '&day=' + today()[:10]):
            report = self.client.get(query).json
            self.assertEqual(report['totals']['revenue'], 270000)
            self.assertEqual(report['totals']['commission'], 126000)
            self.assertEqual(sum(r['commission'] for r in report['employees']), 126000)
            self.assertEqual(sum(r['commission'] for r in report['daily']), 126000)
            self.assertEqual(sum(s['commission'] for e in report['employees'] for s in e['services']), 126000)
        self.assertIn('126000', self.client.get('/api/report.csv?group=day').get_data(as_text=True))

    def test_missing_rule_upgrade_refuses_to_write_when_backup_fails(self):
        from unittest.mock import patch
        from web_api import upgrade_unconfigured_commissions
        order_id = self.save(self.payload()).json['id']
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE web_order_items SET commission=0,rule_snapshot='Chưa cấu hình · 0đ'")
            connection.execute('UPDATE web_order_meta SET commission=0')
        with closing(sqlite3.connect(self.path)) as connection:
            with patch('backup.snapshot', side_effect=OSError('Test backup failure')):
                with self.assertRaises(OSError):
                    upgrade_unconfigured_commissions(connection, self.path)
            self.assertFalse(connection.in_transaction)
            self.assertEqual(connection.execute('SELECT SUM(commission) FROM web_order_items').fetchone()[0], 0)
            self.assertEqual(connection.execute('SELECT commission FROM web_order_meta WHERE order_id=?', (order_id,)).fetchone()[0], 0)

    def test_corrected_missing_rule_commission_reverses_on_void_date(self):
        from web_api import upgrade_unconfigured_commissions
        order_id = self.save(self.payload()).json['id']
        self.assertEqual(self.post(f'/api/orders/{order_id}/void', {'reason':'Test void'}).status_code, 200)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE web_order_items SET commission=0,rule_snapshot='Chưa cấu hình · 0đ' WHERE order_id=?", (order_id,))
            connection.execute('UPDATE web_order_meta SET commission=0 WHERE order_id=?', (order_id,))
            connection.execute("UPDATE DonHang SET NgayGio='2020-12-31 10:00:00' WHERE ID=?", (order_id,))
            connection.execute("UPDATE web_order_meta SET voided_at='2021-01-01T11:00:00+07:00' WHERE order_id=?", (order_id,))
        with closing(sqlite3.connect(self.path)) as connection:
            upgrade_unconfigured_commissions(connection, self.path)
        for month, expected in [('2020-12',135000),('2021-01',-135000)]:
            report = self.client.get('/api/report?month=' + month).json
            self.assertEqual(report['totals']['commission'], expected)
            self.assertEqual(sum(e['commission'] for e in report['employees']), expected)
            self.assertEqual(sum(d['commission'] for d in report['daily']), expected)
            self.assertTrue(all(e['completed_quantity'] == 0 for e in report['employees']))


    def test_deleting_rule_preserves_paid_snapshots_and_invalidates_old_quote(self):
        self.rule()
        rule_id = self.client.get('/api/catalog').json['rules'][0]['id']
        order_id = self.save(self.payload()).json['id']
        detail_before = self.client.get(f'/api/orders/{order_id}').json
        report_before = self.client.get('/api/report').json
        pending = dict(self.payload(), request_key='after-delete')
        old_quote = self.post('/api/orders/quote', pending).json['quote']
        self.assertEqual(self.post(f'/api/rules/{rule_id}/delete', {}).status_code, 200)
        self.assertEqual(self.client.get('/api/catalog').json['rules'], [])
        self.assertEqual(self.client.get(f'/api/orders/{order_id}').json, detail_before)
        self.assertEqual(self.client.get('/api/report').json, report_before)
        response = self.post('/api/orders', dict(pending, quote=old_quote))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json['preview']['commission'], 135000)
        self.assertEqual(len(self.client.get('/api/orders').json), 1)
        self.assertEqual(self.post('/api/orders', dict(pending, quote=response.json['quote'])).status_code, 201)

    def test_deleting_inactive_rule_keeps_other_rules_and_explicit_zero(self):
        self.rule(name='Shop rate')
        first = self.client.get('/api/catalog').json['rules'][0]['id']
        self.post(f'/api/rules/{first}/toggle', {})
        self.rule(name='Explicit zero', employee_id=1, value=0)
        self.assertEqual(self.post(f'/api/rules/{first}/delete', {}).status_code, 200)
        rules = self.client.get('/api/catalog').json['rules']
        self.assertEqual([row['name'] for row in rules], ['Explicit zero'])
        preview = self.post('/api/orders/quote', self.payload()).json['preview']
        self.assertEqual([row['commission'] for row in preview['items']], [0,45000])
        self.assertEqual(self.post(f'/api/rules/{first}/delete', {}).status_code, 404)

    def test_rule_delete_requires_login_and_csrf(self):
        self.rule()
        rule_id = self.client.get('/api/catalog').json['rules'][0]['id']
        path = f'/api/web/rules/{rule_id}/delete'
        raw = FlaskClient(self.app)
        self.assertEqual(raw.post(path, json={}).status_code, 403)
        anonymous = raw.get('/api/web/session').json
        self.assertEqual(raw.post(path, json={}, headers={'Authorization':'Bearer ' + anonymous['token'], 'X-CSRF-Token':anonymous['csrf']}).status_code, 401)
        self.assertEqual(self.client.post(path, json={}).status_code, 403)
        self.assertEqual(self.client.post(path, json={}, headers={'X-CSRF-Token':'wrong'}).status_code, 403)
        self.assertEqual(len(self.client.get('/api/catalog').json['rules']), 1)


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


