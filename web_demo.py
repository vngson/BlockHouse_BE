"""Sample data for an explicitly isolated --demo database."""
import sqlite3
from contextlib import closing
from web_api import today


def seed_demo(database):
    with closing(sqlite3.connect(database)) as db, db:
        if db.execute('SELECT COUNT(*) FROM NhanVien').fetchone()[0]:
            return
        db.execute("INSERT INTO web_users(id,name,password) VALUES(1,'demo','demo-no-password-login')")
        names = ['Minh Anh', 'Hoàng Nam', 'Tuấn Phong']
        for name in names:
            db.execute('INSERT INTO web_employees(name,phone,active) VALUES(?,?,1)', (name,''))
        services = [('Cắt tóc nam',100000),('Cắt & gội',150000),('Uốn tạo kiểu',450000),('Nhuộm tóc',350000),('Gội đầu thư giãn',50000),('Cạo mặt',40000)]
        for name,price in services:
            db.execute('INSERT INTO web_services(name,price,active) VALUES(?,?,1)', (name,price))
        db.execute("INSERT INTO web_commission_rules(name,kind,value,basis,starts) VALUES('Hoa hồng mặc định','percent',4000,'after','2020-01-01')")
        stamp = today()
        for day in range(1,int(stamp[8:10])+1):
            for n in range(2+day%4):
                index = (day*3+n)%len(services)
                employee = (day+n)%3
                name,price = services[index]
                discount = 10000 if day%5==0 else 0
                total,commission = price-discount,(price-discount)*40//100
                created = f'{stamp[:8]}{day:02} {9+n*2:02}:{(day*7+n*11)%60:02}:00'
                order_id = db.execute('INSERT INTO DonHang(NgayGio,NhanVienID,TongTien) VALUES(?,?,?)',(created,employee+1,total)).lastrowid
                db.execute('INSERT INTO DonHang_DichVu(DonHangID,DichVuID,SoLuong) VALUES(?,?,1)',(order_id,index+1))
                db.execute("INSERT INTO web_order_meta(order_id,discount,commission,payment,note,status,request_key,created_by) VALUES(?,?,?,?,?,'paid',?,1)",(order_id,discount,commission,'cash' if n%2 else 'transfer','Dữ liệu minh họa',f'demo-{day}-{n}'))
                db.execute('INSERT INTO web_order_items(order_id,service_id,employee_id,service_name,employee_name,quantity,price,discount,total,commission,rule_snapshot) VALUES(?,?,?,?,?,1,?,?,?,?,?)',(order_id,index+1,employee+1,name,names[employee],price,discount,total,commission,'Hoa hồng mặc định · 40% · sau giảm giá'))
