from datetime import date, datetime

from sqlalchemy import func, or_
from models.employee_model import Employee
from models import db
from typing import Dict, List, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class EmployeeService:
    """
    Service layer for handling employee-related business logic.
    """
    
    @staticmethod
    def get_all_employees(
        start_date: date = None,
        end_date: date  = None,
        keyword: str = None,
        page: int = 1,
        page_size: int = 15
    ):
        query = Employee.query

        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        # SỬA LẠI: Sử dụng func.date() để chuyển datetime thành date trước khi so sánh
        if start_date:
            query = query.filter(func.date(Employee.created_at) >= start_date)

        if end_date:
            query = query.filter(func.date(Employee.created_at) <= end_date)

        if keyword:
            query = query.filter(Employee.name.ilike(f"%{keyword}%"))

        total_employees = query.count()
        employees = (
            query
            .order_by(Employee.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return employees, total_employees

    @staticmethod
    def get_employee(employee_id: int) -> Employee:
        """
        Retrieve an employee by ID.
        
        Args:
            employee_id: ID of the employee to retrieve
        
        Returns:
            Employee object if found
            
        Raises:
            ValueError: If employee is not found
        """
        employee = Employee.query.get(employee_id)
        if not employee:
            raise ValueError(f"Employee with ID {employee_id} not found")
        return employee

    @staticmethod
    def create_employee(data: Dict[str, Any]) -> Employee:
        """
        Create a new employee.
        
        Args:
            data: Dictionary containing employee data
            
        Returns:
            Created Employee object
        """
        employee = Employee(**data)
        db.session.add(employee)
        db.session.commit()
        return employee

    @staticmethod
    def update_employee(employee_id: int, data: Dict[str, Any]) -> Employee:
        """
        Update an existing employee.
        
        Args:
            employee_id: ID of the employee to update
            data: Dictionary containing updated employee data
            
        Returns:
            Updated Employee object
            
        Raises:
            ValueError: If employee is not found
        """
        employee = Employee.query.get(employee_id)
        if not employee:
            raise ValueError(f"Employee with ID {employee_id} not found")
        
        for key, value in data.items():
            setattr(employee, key, value)
            
        db.session.commit()
        return employee

    @staticmethod
    def delete_employee(employee_id: int) -> None:
        """
        Delete an employee.
        
        Args:
            employee_id: ID of the employee to delete
            
        Raises:
            ValueError: If employee is not found
        """
        employee = Employee.query.get(employee_id)
        if not employee:
            raise ValueError(f"Employee with ID {employee_id} not found")
        
        db.session.delete(employee)
        db.session.commit()# Business logic for employee operations would go here