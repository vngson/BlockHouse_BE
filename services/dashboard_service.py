from models import db
from models.employee_model import Employee
from models.order_model import Order
from models.order_service_model import OrderServiceModel
from datetime import datetime, timedelta
from sqlalchemy import func
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class DashboardService:
    """
    Service layer for handling dashboard-related business logic.
    """

    @staticmethod
    def get_dashboard_data(month: Optional[int] = None, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieve dashboard data for the specified or current month/year.
        
        Args:
            month: Optional month (1-12), defaults to current month
            year: Optional year, defaults to current year
        
        Returns:
            Dictionary containing dashboard data
        """
        now = datetime.now()
        target_month = month if month is not None else now.month
        target_year = year if year is not None else now.year

        # 1. Top 4 employees with highest revenue
        top_employees = (
            db.session.query(
                Employee.id,
                Employee.name,
                func.sum(Order.total).label("revenue"),
                func.count(Order.id).label("order_count")
            )
            .join(Order, Order.employee_id == Employee.id)
            .filter(
                Employee.status == 1,
                func.strftime('%m', Order.datetime) == f'{target_month:02d}',
                func.strftime('%Y', Order.datetime) == str(target_year)
            )
            .group_by(Employee.id, Employee.name)
            .order_by(func.sum(Order.total).desc())
            .limit(4)
            .all()
        )

        top_employees_data = [
            {
                "id": emp.id,
                "name": emp.name,
                "revenue": float(emp.revenue),
                "order_count": int(emp.order_count)
            } for emp in top_employees
        ]

        # 2. Total service sales (sum of all service quantities sold)
        total_service_sales = (
            db.session.query(func.sum(OrderServiceModel.quantity))
            .join(Order, Order.id == OrderServiceModel.order_id)
            .filter(
                func.strftime('%m', Order.datetime) == f'{target_month:02d}',
                func.strftime('%Y', Order.datetime) == str(target_year)
            )
            .scalar() or 0
        )

        # 3. Total revenue
        total_revenue = (
            db.session.query(func.sum(Order.total))
            .filter(
                func.strftime('%m', Order.datetime) == f'{target_month:02d}',
                func.strftime('%Y', Order.datetime) == str(target_year)
            )
            .scalar() or 0
        )

        # 4. Growth compared to last month
        last_month_date = (datetime(target_year, target_month, 1) - timedelta(days=1))
        last_month = last_month_date.month
        last_month_year = last_month_date.year

        last_month_revenue = (
            db.session.query(func.sum(Order.total))
            .filter(
                func.strftime('%m', Order.datetime) == f'{last_month:02d}',
                func.strftime('%Y', Order.datetime) == str(last_month_year)
            )
            .scalar() or 0
        )

        if last_month_revenue == 0:
            growth = 100.0 if total_revenue > 0 else 0.0
        else:
            growth = ((total_revenue - last_month_revenue) / last_month_revenue) * 100

        # 5. Revenue by month for the current year
        monthly_revenue = (
            db.session.query(
                func.strftime('%m', Order.datetime).label("month"),
                func.sum(Order.total).label("revenue")
            )
            .filter(func.strftime('%Y', Order.datetime) == str(target_year))
            .group_by(func.strftime('%m', Order.datetime))
            .order_by(func.strftime('%m', Order.datetime))
            .all()
        )

        chart_data = [{"month": int(month), "revenue": float(revenue)} for month, revenue in monthly_revenue]

        return {
            "top_employees": top_employees_data,
            "total_revenue": float(total_revenue),
            "total_service_sales": int(total_service_sales),
            "growth_percent": round(growth, 2),
            "monthly_chart": chart_data
        }