from datetime import datetime as dt
from . import db

class Service(db.Model):
    __tablename__ = 'DichVu'
    id = db.Column('ID', db.Integer, primary_key=True)
    name = db.Column('Ten', db.String(100), nullable=False)
    description = db.Column('MoTa', db.Text)
    price = db.Column('Gia', db.Float, nullable=False)
    created_at = db.Column('created_at', db.DateTime, default=dt.utcnow)
    updated_at = db.Column('updated_at', db.DateTime, default=dt.utcnow, onupdate=dt.utcnow)