from datetime import datetime as dt
from . import db

class Promotion(db.Model):
    __tablename__ = 'KhuyenMai'
    id = db.Column('ID', db.Integer, primary_key=True)
    name = db.Column('Ten', db.String(100), nullable=False)
    description = db.Column('MoTa', db.Text)
    start_date = db.Column('NgayBatDau', db.Date)
    end_date = db.Column('NgayKetThuc', db.Date)
    value = db.Column('GiaTri', db.Float, nullable=False)
    type = db.Column('Loai', db.String(10))
    created_at = db.Column('created_at', db.DateTime, default=dt.utcnow)
    updated_at = db.Column('updated_at', db.DateTime, default=dt.utcnow, onupdate=dt.utcnow)