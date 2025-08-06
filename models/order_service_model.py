from datetime import datetime as dt
from . import db

class OrderServiceModel(db.Model):
    __tablename__ = 'DonHang_DichVu'
    order_id = db.Column('DonHangID', db.Integer, db.ForeignKey('DonHang.ID'), primary_key=True)
    service_id = db.Column('DichVuID', db.Integer, db.ForeignKey('DichVu.ID'), primary_key=True)
    quantity = db.Column('SoLuong', db.Integer, default=1)
    created_at = db.Column('created_at', db.DateTime, default=dt.utcnow)
    updated_at = db.Column('updated_at', db.DateTime, default=dt.utcnow, onupdate=dt.utcnow)