from datetime import datetime as dt
from . import db

class Order(db.Model):
    __tablename__ = 'DonHang'
    id = db.Column('ID', db.Integer, primary_key=True)
    datetime = db.Column('NgayGio', db.DateTime, nullable=False)
    employee_id = db.Column('NhanVienID', db.Integer, db.ForeignKey('NhanVien.ID'))
    promotion_id = db.Column('KhuyenMaiID', db.Integer, db.ForeignKey('KhuyenMai.ID'))
    total = db.Column('TongTien', db.Float)
    created_at = db.Column('created_at', db.DateTime, default=dt.utcnow)
    updated_at = db.Column('updated_at', db.DateTime, default=dt.utcnow, onupdate=dt.utcnow)