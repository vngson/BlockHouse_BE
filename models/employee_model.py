from datetime import datetime as dt
from . import db
from typing import Optional

from enum import Enum

class EmployeeStatus(Enum):
    """Enum class for employee status codes"""
    ACTIVE = 1
    INACTIVE = 0

class Employee(db.Model):
    """
    Employee model for database operations.
    """
    __tablename__ = 'NhanVien'
    id = db.Column('ID', db.Integer, primary_key=True)
    phone = db.Column('SDT', db.String(20), nullable=True)
    name = db.Column('Ten', db.String(100), nullable=False)
    phone = db.Column('SDT', db.String(20))
    status = db.Column('TrangThai', db.Integer, default=EmployeeStatus.ACTIVE)
    income = db.Column('ThuNhap', db.Float)
    created_at = db.Column('created_at', db.DateTime, default=dt.utcnow)
    updated_at = db.Column('updated_at', db.DateTime, default=dt.utcnow, onupdate=dt.utcnow)

    def __repr__(self) -> str:
        return f"<Employee {self.name} (ID: {self.id})>"