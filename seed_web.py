"""Populate the normal database with complete, explicitly requested sample data."""
import argparse
import calendar
import random
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from werkzeug.security import generate_password_hash
from web_api import today


def seed_database(database, reset=False, username='admin', password='BlockHouse@123'):
    now = datetime.fromisoformat(today())
    stamp = now.strftime('%Y-%m-%d %H:%M:%S')
    rng = random.Random(20261025)
    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        populated = connection.execute('SELECT COUNT(*) FROM NhanVien').fetchone()[0]
        if populated and not reset:
            raise ValueError('Database contains data. Pass --reset to replace the sample dataset.')
        backup_path = Path(database).with_name(Path(database).name + now.strftime('.before-seed-%Y%m%d-%H%M%S.bak'))
        with closing(sqlite3.connect(backup_path)) as backup:
            connection.backup(backup)
        with connection:
            for table in ('web_sessions','web_order_items','web_order_meta','DonHang_DichVu','DonHang','web_commission_rules','web_service_state','KhuyenMai','NhanVien','DichVu','web_users'):
                connection.execute(f'DELETE FROM {table}')
            connection.execute("DELETE FROM sqlite_sequence WHERE name IN ('NhanVien','DichVu','DonHang','KhuyenMai')")
            connection.execute('INSERT INTO web_users(id,name,password) VALUES(1,?,?)',(username,generate_password_hash(password)))
            employees = [('Hoàng Nam','0901000101',1),('Minh Anh','0901000102',1),('Tuấn Phong','0901000103',1),('Đức Huy','0901000104',1),('Gia Bảo','0901000105',1),('Quốc Việt','0901000106',0)]
            for employee_id,(name,phone,active) in enumerate(employees,1):
                connection.execute('INSERT INTO NhanVien(ID,Ten,SDT,TrangThai,ThuNhap,created_at,updated_at) VALUES(?,?,?,?,0,?,?)',(employee_id,name,phone,active,stamp,stamp))
            services = [('Cắt tóc nam',100000,'Cắt và tạo kiểu theo khuôn mặt'),('Cắt & gội',150000,'Combo cắt tóc và gội đầu'),('Gội đầu thư giãn',50000,'Gội và massage da đầu'),('Cạo mặt',40000,'Cạo mặt và chăm sóc cơ bản'),('Uốn tạo kiểu',450000,'Uốn và tạo độ phồng'),('Nhuộm tóc',350000,'Nhuộm màu theo yêu cầu'),('Tẩy tóc',500000,'Tẩy nền trước khi nhuộm'),('Phục hồi tóc',250000,'Dưỡng và phục hồi tóc hư tổn'),('Tạo kiểu / vuốt sáp',30000,'Tạo kiểu nhanh'),('Cắt tóc trẻ em',80000,'Dịch vụ cắt tóc cho bé'),('Chăm sóc da mặt',180000,'Làm sạch và chăm sóc da'),('Combo mùa hè',120000,'Gói cũ đã ngừng áp dụng')]
            for service_id,(name,price,description) in enumerate(services,1):
                connection.execute('INSERT INTO DichVu(ID,Ten,Gia,MoTa,created_at,updated_at) VALUES(?,?,?,?,?,?)',(service_id,name,price,description,stamp,stamp))
                connection.execute('INSERT INTO web_service_state(service_id,active) VALUES(?,?)',(service_id,0 if service_id==12 else 1))
            current_start=now.strftime('%Y-%m-01')
            rules = [
                ('Mặc định toàn shop',None,None,'percent',4000,'after','2020-01-01',1),
                ('Thợ chính Hoàng Nam',1,None,'percent',4500,'after',current_start,1),
                ('Hoa hồng gội đầu',None,3,'fixed',15000,'after','2020-01-01',1),
                ('Minh Anh thực hiện gội đầu',2,3,'fixed',20000,'after','2020-01-01',1),
                ('Hoa hồng uốn tạo kiểu',None,5,'percent',3500,'before','2020-01-01',1),
                ('Hoàng Nam uốn tạo kiểu',1,5,'percent',5000,'after','2020-01-01',1),
                ('Ưu đãi hoa hồng cũ',None,12,'percent',3000,'after','2020-01-01',0),
            ]
            for rule in rules:
                connection.execute('INSERT INTO web_commission_rules(name,employee_id,service_id,kind,value,basis,starts,active) VALUES(?,?,?,?,?,?,?,?)',rule)
            months=[]
            first=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
            for n in range(3):
                months.append(first)
                first=(first-timedelta(days=1)).replace(day=1)
            order_id=0
            for month_start in reversed(months):
                last_day=now.day if month_start.month==now.month and month_start.year==now.year else calendar.monthrange(month_start.year,month_start.month)[1]
                for day in range(1,last_day+1):
                    day_stamp=month_start.replace(day=day)
                    count=rng.randint(18,42) if day_stamp.weekday()<5 else rng.randint(32,50)
                    is_today=day_stamp.date()==now.date()
                    if is_today:
                        elapsed=max(0,min(660,now.hour*60+now.minute-9*60))
                        count=int(count*elapsed/660)
                    for number in range(count):
                        minute=9*60+int((number+1)*660/(count+1))
                        if is_today:
                            minute=9*60+int((number+1)*max(1,elapsed)/(count+1))
                        created=day_stamp.replace(hour=minute//60,minute=minute%60)
                        items=[]
                        chosen=rng.sample(list(range(1,12)),rng.choices([1,2,3],[65,30,5])[0])
                        for service_id in chosen:
                            employee_id=rng.randint(1,6 if month_start<months[0] else 5)
                            if service_id==3 and rng.random()<0.55:
                                employee_id=2
                            quantity=2 if rng.random()<0.025 else 1
                            name,price,_description=services[service_id-1]
                            items.append(dict(service_id=service_id,employee_id=employee_id,service_name=name,employee_name=employees[employee_id-1][0],quantity=quantity,price=price,gross=price*quantity))
                        gross=sum(i['gross'] for i in items)
                        discount=gross*rng.choices([0,5,10,15],[74,12,10,4])[0]//100
                        allocated=[discount*i['gross']//gross for i in items]
                        remainder=sorted(range(len(items)),key=lambda n:discount*items[n]['gross']%gross,reverse=True)
                        for n in remainder[:discount-sum(allocated)]:
                            allocated[n]+=1
                        for i,line_discount in zip(items,allocated):
                            i['discount']=line_discount
                            i['total']=i['gross']-line_discount
                            candidates=[r for r in rules if r[7] and r[6]<=created.strftime('%Y-%m-%d') and r[1] in (None,i['employee_id']) and r[2] in (None,i['service_id'])]
                            rule=max(candidates,key=lambda r:((2 if r[1] else 0)+(1 if r[2] else 0),r[6]))
                            base=i['gross'] if rule[5]=='before' else i['total']
                            amount=Decimal(base)*rule[4]/10000 if rule[3]=='percent' else Decimal(rule[4]*i['quantity'])
                            i['commission']=int(amount.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                            rate=f'{rule[4]/100:g}%' if rule[3]=='percent' else f'{rule[4]:,}đ/lượt'
                            i['snapshot']=f"{rule[0]} · {rate} · {'trước' if rule[5]=='before' else 'sau'} giảm giá"
                        order_id+=1
                        created_text=created.strftime('%Y-%m-%d %H:%M:%S')
                        total=gross-discount
                        commission=sum(i['commission'] for i in items)
                        workers={i['employee_id'] for i in items}
                        assigned=next(iter(workers)) if len(workers)==1 else None
                        connection.execute('INSERT INTO DonHang(ID,NgayGio,NhanVienID,TongTien,created_at,updated_at) VALUES(?,?,?,?,?,?)',(order_id,created_text,assigned,total,created_text,created_text))
                        grouped={}
                        for i in items:
                            grouped[i['service_id']]=grouped.get(i['service_id'],0)+i['quantity']
                            connection.execute('INSERT INTO web_order_items(order_id,service_id,employee_id,service_name,employee_name,quantity,price,discount,total,commission,rule_snapshot) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(order_id,i['service_id'],i['employee_id'],i['service_name'],i['employee_name'],i['quantity'],i['price'],i['discount'],i['total'],i['commission'],i['snapshot']))
                        for service_id,quantity in grouped.items():
                            connection.execute('INSERT INTO DonHang_DichVu(DonHangID,DichVuID,SoLuong,created_at,updated_at) VALUES(?,?,?,?,?)',(order_id,service_id,quantity,created_text,created_text))
                        voided=created+timedelta(days=rng.randint(0,3),hours=1)
                        cancelled=rng.random()<0.025 and voided<=now
                        payment=rng.choices(['cash','transfer'],[45,55])[0]
                        note=rng.choice(['Khách vãng lai','Khách hẹn trước','Khách quen',''])
                        void_time=voided.isoformat(timespec='seconds') if cancelled else None
                        connection.execute('INSERT INTO web_order_meta(order_id,discount,commission,payment,note,status,request_key,voided_at,void_reason,created_by) VALUES(?,?,?,?,?,?,?,?,?,1)',(order_id,discount,commission,payment,note,'void' if cancelled else 'paid',f'seed-normal-{order_id}',void_time,'Khách đổi dịch vụ / hoàn tiền' if cancelled else None))
            connection.execute('UPDATE NhanVien SET ThuNhap=COALESCE((SELECT SUM(i.total) FROM web_order_items i JOIN web_order_meta m ON m.order_id=i.order_id WHERE i.employee_id=NhanVien.ID AND m.status=\'paid\'),0)')
            mismatches=connection.execute('SELECT COUNT(*) FROM DonHang d JOIN web_order_meta m ON m.order_id=d.ID WHERE CAST(d.TongTien AS INTEGER)<>(SELECT SUM(i.total) FROM web_order_items i WHERE i.order_id=d.ID) OR m.commission<>(SELECT SUM(i.commission) FROM web_order_items i WHERE i.order_id=d.ID)').fetchone()[0]
            if mismatches:
                raise AssertionError('Seed invoice totals do not reconcile')
            if connection.execute('PRAGMA foreign_key_check').fetchall():
                raise AssertionError('Seed foreign keys are invalid')
            summary=dict(database=str(database),employees=len(employees),services=len(services),rules=len(rules),orders=order_id,months=[m.strftime('%Y-%m') for m in months],voided=connection.execute("SELECT COUNT(*) FROM web_order_meta WHERE status='void'").fetchone()[0])
            return summary


if __name__=='__main__':
    import json
    import sys
    if sys.stdout:
        sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='Seed the regular BlockHouse database with sample data')
    parser.add_argument('--reset',action='store_true',help='Replace the existing sample dataset')
    parser.add_argument('--username',default='admin')
    parser.add_argument('--password',default='BlockHouse@123')
    args=parser.parse_args()
    from app import create_app
    app=create_app()
    print(json.dumps(seed_database(app.config['WEB_DATABASE'],args.reset,args.username,args.password),ensure_ascii=False))
