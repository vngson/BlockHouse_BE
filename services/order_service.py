from datetime import date, timedelta
import datetime

from sqlalchemy import desc, func,distinct, tuple_
from models.employee_model import Employee
from models.order_model import Order
from models.order_service_model import OrderServiceModel
from models import db
from typing import Dict, List, Any, Tuple
import logging

from models.promotion_model import Promotion
from models.service_model import Service

from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

class OrderService:
    """
    Service layer for handling order-related business logic.
    """
    
    def get_all_orders(
        date_from: date = None,
        date_to: date = None,
        keyword: str = None,
        page: int = 1,
        page_size: int = 15
    ) -> Tuple[List[Order], int]:
        """
        Retrieve orders with optional date filtering, keyword search, and pagination.
        
        Args:
            date_from: Filter orders created on or after this date
            date_to: Filter orders created on or before this date
            keyword: Search term to filter orders by employee name or service name
            page: Page number for pagination
            page_size: Number of orders per page

        Returns:
            Tuple containing list of Order objects and total count
        """
        query = Order.query

        if date_from:
            query = query.filter(func.date(Order.datetime) >= date_from)
        if date_to:
            query = query.filter(func.date(Order.datetime) <= date_to)
        
        if keyword:
            query = query.join(OrderServiceModel, isouter=True).join(Service, isouter=True).join(Employee, isouter=True).filter(
                db.or_(
                    Employee.name.ilike(f"%{keyword}%") if Employee else False,
                    Service.name.ilike(f"%{keyword}%") if Service else False
                )
            )

        total_orders = query.count()
        orders = query.order_by(desc(Order.datetime)).offset((page - 1) * page_size).limit(page_size).all()

        for order in orders:
            order.services = OrderServiceModel.query.filter_by(order_id=order.id).all()
            if order.employee_id:
                employee = Employee.query.get(order.employee_id)
                order.employee_name = employee.name if employee else None
            else:
                order.employee_name = None

            for service in order.services:
                if service.service_id:
                    service_item = Service.query.get(service.service_id)
                    service.name = service_item.name if service_item else None
                else:
                    service.name = None

        return orders, total_orders
    
    
    @staticmethod
    def get_orders_by_date(
        date_from: date = None,
        date_to: date = None,
        keyword: str = None,
        page: int = 1,
        page_size: int = 15
    ) -> Tuple[List[Dict], int]:
        date_query = db.session.query(func.date(Order.datetime).label('order_date')).distinct()
        if date_from:
            date_query = date_query.filter(func.date(Order.datetime) >= date_from)
        if date_to:
            date_query = date_query.filter(func.date(Order.datetime) <= date_to)
        total_days = date_query.count()

        paginated_dates = date_query.order_by(func.date(Order.datetime).desc())\
                                    .offset((page - 1) * page_size).limit(page_size).all()
        order_dates = [d.order_date for d in paginated_dates]

        orders_query = Order.query.filter(func.date(Order.datetime).in_(order_dates))
        if keyword:
            orders_query = orders_query.join(Employee, Order.employee_id == Employee.id, isouter=True)\
                                      .join(OrderServiceModel, Order.id == OrderServiceModel.order_id, isouter=True)\
                                      .join(Service, OrderServiceModel.service_id == Service.id, isouter=True)\
                                      .filter(db.or_(
                                          Employee.name.ilike(f"%{keyword}%") if Employee else False,
                                          Service.name.ilike(f"%{keyword}%")
                                      ))

        orders = orders_query.order_by(Order.datetime.desc()).all()

        orders_by_date = {}
        for order in orders:
            order_date = order.datetime.date()
            if order_date not in orders_by_date:
                orders_by_date[order_date] = {
                    'date': order_date,
                    'total': 0.0,
                    'services': [],
                    'employee_id': None,
                    'promotion_id': None
                }

            order_services = OrderServiceModel.query.filter_by(order_id=order.id).all()
            calculated_total = 0.0
            for os in order_services:
                service = Service.query.get(os.service_id)
                if service:
                    calculated_total += service.price * os.quantity
                    existing_service = next(
                        (s for s in orders_by_date[order_date]['services'] if s['service_id'] == service.id),
                        None
                    )
                    if existing_service:
                        existing_service['quantity'] += os.quantity
                    else:
                        orders_by_date[order_date]['services'].append({
                            'service_id': service.id,
                            'name': service.name,
                            'quantity': os.quantity
                        })

            orders_by_date[order_date]['total'] += calculated_total
            if orders_by_date[order_date]['promotion_id'] is None:
                orders_by_date[order_date]['promotion_id'] = order.promotion_id

        result = list(orders_by_date.values())
        return result, total_days
    
    @staticmethod
    def get_revenue_by_employee(
        date_from: date = None,
        date_to: date = None,
        keyword: str = None,
        page: int = 1,
        page_size: int = 15
    ) -> Tuple[List[Dict], int]:
        """
        Retrieve revenue grouped by date and employee with optional date filtering, keyword search, and pagination.
        
        Args:
            date_from: Filter orders created on or after this date
            date_to: Filter orders created on or before this date
            keyword: Search term to filter orders by employee name or service name
            page: Page number for pagination
            page_size: Number of records per page

        Returns:
            Tuple containing list of revenue entries (date, employee, total, services) and total count of date-employee combinations
        """
        logger.debug(f"Fetching revenue by employee with date_from={date_from}, date_to={date_to}, keyword={keyword}, page={page}, page_size={page_size}")
        date_employee_query = db.session.query(
            func.date(Order.datetime).label('order_date'),
            Order.employee_id
        ).distinct()

        if date_from:
            date_employee_query = date_employee_query.filter(func.date(Order.datetime) >= date_from)
        if date_to:
            date_employee_query = date_employee_query.filter(func.date(Order.datetime) <= date_to)
        total_date_employees = date_employee_query.count()
    
        # Paginate date-employee combinations and sort by date in descending order
        paginated_date_employees = date_employee_query.order_by(
            func.date(Order.datetime).desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        
        date_employee_pairs = [(d.order_date, d.employee_id) for d in paginated_date_employees]
        
        # Get orders for these date-employee pairs
        orders_query = Order.query.filter(
            tuple_(func.date(Order.datetime), Order.employee_id).in_(date_employee_pairs)
        )
        
        if keyword:
            orders_query = orders_query.join(Employee, Order.employee_id == Employee.id, isouter=True)\
                                    .join(OrderServiceModel, Order.id == OrderServiceModel.order_id, isouter=True)\
                                    .join(Service, OrderServiceModel.service_id == Service.id, isouter=True)\
                                    .filter(db.or_(
                                        Employee.name.ilike(f"%{keyword}%") if Employee else False,
                                        Service.name.ilike(f"%{keyword}%")
                                    ))
        
        orders = orders_query.order_by(Order.datetime.desc()).all()


        # Group by date and employee
        revenue_by_employee = {}
        for order in orders:
            order_date = order.datetime.date()
            employee_id = order.employee_id
            if not employee_id:
                continue  # Skip orders without an employee
            key = (order_date, employee_id)
            if key not in revenue_by_employee:
                employee = Employee.query.get(employee_id)
                revenue_by_employee[key] = {
                    'date': order_date,
                    'employee_id': employee_id,
                    'employee_name': employee.name if employee else None,
                    'total': 0.0,
                    'services': []
                }

            # Calculate total from services
            order_services = OrderServiceModel.query.filter_by(order_id=order.id).all()
            for os in order_services:
                service = Service.query.get(os.service_id)
                if service:
                    service_total = service.price * os.quantity
                    revenue_by_employee[key]['total'] += service_total
                    existing_service = next(
                        (s for s in revenue_by_employee[key]['services'] if s['service_id'] == service.id),
                        None
                    )
                    if existing_service:
                        existing_service['quantity'] += os.quantity
                    else:
                        revenue_by_employee[key]['services'].append({
                            'service_id': service.id,
                            'name': service.name,
                            'quantity': os.quantity
                        })

        result = list(revenue_by_employee.values())
        return result, total_date_employees
    

    @staticmethod
    def get_orders_for_one_date(order_date: date) -> Tuple[List[Dict], int]:
        """
        Retrieve all orders for a specific date, grouped and combined into one entry.
        
        Args:
            order_date: The specific date to fetch orders for.

        Returns:
            Tuple containing list of dictionaries (one entry for the date) and total count of orders
        """
        logger.debug(f"Fetching orders for one datenict={order_date}")

        # Query all orders for the given date with services
        query = db.session.query(
            Order,
            OrderServiceModel,
            Service
        ).outerjoin(
            OrderServiceModel, Order.id == OrderServiceModel.order_id
        ).outerjoin(
            Service, OrderServiceModel.service_id == Service.id
        ).filter(
            func.date(Order.datetime) == order_date
        )

        orders_with_services = query.order_by(Order.datetime.desc()).all()

        if not orders_with_services:
            return [], 0

        # Group and combine
        combined = {
            'date': order_date,
            'total': 0,
            'services': [],
            'employee_id': None,
            'promotion_id': None
        }

        total_orders = 0
        for order, order_service, service in orders_with_services:
            total_orders += 1
            combined['total'] += order.total or 0
            if combined['promotion_id'] is None:
                combined['promotion_id'] = order.promotion_id

            if order_service and service:  # Ensure both order_service and service exist
                existing_service = next(
                    (s for s in combined['services'] if s['service_id'] == service.id),
                    None
                )
                if existing_service:
                    existing_service['quantity'] += order_service.quantity
                else:
                    combined['services'].append({
                        'service_id': service.id,
                        'name': service.name,
                        'quantity': order_service.quantity
                    })

        return [combined], total_orders

    @staticmethod
    def get_orders_by_date_and_employee(
        order_date: date,
        employee_id: int
    ) -> Tuple[Dict, int]:
        """
        Retrieve all orders for a specific date and employee ID.

        Args:
            order_date: The specific date to filter orders
            employee_id: The ID of the employee to filter orders

        Returns:
            Tuple containing a dictionary with order details and total order count
        """
        logger.debug(f"Fetching orders for date={order_date}, employee_id={employee_id}")
        
        # Query orders for the specific date and employee
        orders_query = Order.query.filter(
            func.date(Order.datetime) == order_date,
            Order.employee_id == employee_id
        )
        
        orders = orders_query.order_by(Order.datetime.desc()).all()
        total_orders = len(orders)
        
        # Build response
        result = {
            'date': order_date,
            'employee_id': employee_id,
            'employee_name': None,
            'total': 0.0,
            'services': []
        }
        
        if orders:
            employee = Employee.query.get(employee_id)
            result['employee_name'] = employee.name if employee else None
            
            # Calculate total and aggregate services
            for order in orders:
                order_services = OrderServiceModel.query.filter_by(order_id=order.id).all()
                for os in order_services:
                    service = Service.query.get(os.service_id)
                    if service:
                        result['total'] += service.price * os.quantity
                        existing_service = next(
                            (s for s in result['services'] if s['service_id'] == service.id),
                            None
                        )
                        if existing_service:
                            existing_service['quantity'] += os.quantity
                        else:
                            result['services'].append({
                                'service_id': service.id,
                                'name': service.name,
                                'quantity': os.quantity
                            })
        
        return result, total_orders

    @staticmethod
    def get_order(order_id: int) -> Order:
        """
        Retrieve an order by ID with associated services.
        
        Args:
            order_id: ID of the order to retrieve

        Returns:
            Order object if found

        Raises:
            ValueError: If order is not found
        """
        order = Order.query.get(order_id)
        if not order:
            raise ValueError(f"Order with ID {order_id} not found")
        
        # Load associated services
        order.services = OrderServiceModel.query.filter_by(order_id=order_id).all()
        order.employee_name = Employee.query.get(order.employee_id).name if order.employee_id else None
        for service in order.services:
            if service.service_id:
                service_item = Service.query.get(service.service_id)
                service.name = service_item.name if service_item else None
            else:
                service.name = None
        return order

    @staticmethod
    def calculate_order_total(services_data, promotion_id=None):
        """Tính total từ services."""
        total = 0.0
        for service in services_data:
            svc = Service.query.get(service['service_id'])
            if not svc:
                raise ValueError(f"Service ID {service['service_id']} not found")
            total += svc.price * service['quantity']
        return total

    @staticmethod
    def update_employee_income(employee_id, amount):
        """Cập nhật income, đảm bảo không âm."""
        if employee_id:
            emp = Employee.query.get(employee_id)
            if not emp:
                raise ValueError(f"Employee ID {employee_id} not found")
            new_income = (emp.income or 0.0) + amount
            if new_income < 0:
                logger.warning(f"Prevented negative income for employee {employee_id}: {new_income}")
                new_income = 0.0  # Hoặc raise ValueError tùy yêu cầu
            emp.income = new_income

    @staticmethod
    def create_order(data: Dict[str, Any]) -> Order:
        services_data = data.pop('services', [])
        if not services_data:
            raise ValueError("At least one service required")

        calculated_total = OrderService.calculate_order_total(services_data)
        if 'total' in data and data['total'] is not None:
            if abs(data['total'] - calculated_total) > 0.01:
                raise ValueError("Provided total does not match calculated total")
        data['total'] = calculated_total

        if data.get('employee_id') and not Employee.query.get(data['employee_id']):
            raise ValueError(f"Employee ID {data['employee_id']} not found")
        if data.get('promotion_id') and not Promotion.query.get(data['promotion_id']):
            raise ValueError(f"Promotion ID {data['promotion_id']} not found")

        with db.session.begin_nested():
            order = Order(**data)
            db.session.add(order)
            db.session.flush()

            for service in services_data:
                order_service = OrderServiceModel(
                    order_id=order.id,
                    service_id=service['service_id'],
                    quantity=service['quantity']
                )
                db.session.add(order_service)

            OrderService.update_employee_income(data.get('employee_id'), calculated_total)
            db.session.commit()

        order.services = OrderServiceModel.query.filter_by(order_id=order.id).all()
        logger.info(f"Created order ID {order.id} with total {calculated_total}")
        return order

    @staticmethod
    def update_order(order_id: int, data: Dict[str, Any]) -> Order:
        order = Order.query.get(order_id)
        if not order:
            raise ValueError(f"Order ID {order_id} not found")

        old_total = order.total or 0.0
        old_employee_id = order.employee_id

        services_data = data.pop('services', None)
        with db.session.begin_nested():
            if services_data is not None:
                OrderServiceModel.query.filter_by(order_id=order_id).delete()
                calculated_total = OrderService.calculate_order_total(services_data)
                for service in services_data:
                    order_service = OrderServiceModel(
                        order_id=order_id,
                        service_id=service['service_id'],
                        quantity=service['quantity']
                    )
                    db.session.add(order_service)
            else:
                calculated_total = old_total
            
            if 'datetime' in data and isinstance(data['datetime'], str):
                try:
                    data['datetime'] = datetime.datetime.fromisoformat(data['datetime'])
                except ValueError:
                    raise ValueError("Invalid datetime format. Expected ISO format (e.g., '2025-10-05T10:04:00')")

            for key, value in data.items():
                setattr(order, key, value)
            order.total = calculated_total

            if old_employee_id != order.employee_id:
                OrderService.update_employee_income(old_employee_id, -old_total)
                OrderService.update_employee_income(order.employee_id, calculated_total)
            else:
                OrderService.update_employee_income(order.employee_id, calculated_total - old_total)

            db.session.commit()

        order.services = OrderServiceModel.query.filter_by(order_id=order_id).all()
        logger.info(f"Updated order ID {order_id} with total {calculated_total}")
        return order

    @staticmethod
    def delete_order(order_id: int) -> None:
        order = Order.query.get(order_id)
        if not order:
            raise ValueError(f"Order ID {order_id} not found")

        with db.session.begin_nested():
            OrderService.update_employee_income(order.employee_id, -(order.total or 0.0))
            OrderServiceModel.query.filter_by(order_id=order_id).delete()
            db.session.delete(order)
            db.session.commit()
        logger.info(f"Deleted order ID {order_id}")

        order = Order.query.get(order_id)
        if not order:
            raise ValueError(f"Order ID {order_id} not found")

        # Trừ income
        OrderService.update_employee_income(order.employee_id, -(order.total or 0.0))

        OrderServiceModel.query.filter_by(order_id=order_id).delete()
        db.session.delete(order)
        db.session.commit()
        """
        Delete an order and its associated services.

        Args:
            order_id: ID of the order to delete

        Raises:
            ValueError: If order is not found
        """
        order = Order.query.get(order_id)
        if not order:
            raise ValueError(f"Order with ID {order_id} not found")

        # Delete associated services
        OrderServiceModel.query.filter_by(order_id=order_id).delete()

        db.session.delete(order)
        db.session.commit()
        logger.info(f"Deleted order ID {order_id}")
    
    # @staticmethod
    # def get_orders_by_date(
    #     date_from: date = None,
    #     date_to: date = None,
    #     keyword: str = None,
    #     page: int = 1,
    #     page_size: int = 15
    # ) -> Tuple[List[Dict], int]:
    #     date_query = db.session.query(func.date(Order.datetime).label('order_date')).distinct()
    #     if date_from:
    #         date_query = date_query.filter(func.date(Order.datetime) >= date_from)
    #     if date_to:
    #         date_query = date_query.filter(func.date(Order.datetime) <= date_to)
    #     total_days = date_query.count()

    #     paginated_dates = date_query.order_by(func.date(Order.datetime).desc())\
    #                                 .offset((page - 1) * page_size).limit(page_size).all()
    #     order_dates = [d.order_date for d in paginated_dates]

    #     orders_query = Order.query.filter(func.date(Order.datetime).in_(order_dates))
    #     if keyword:
    #         orders_query = orders_query.join(Employee, Order.employee_id == Employee.id, isouter=True)\
    #                                   .join(OrderServiceModel, Order.id == OrderServiceModel.order_id, isouter=True)\
    #                                   .join(Service, OrderServiceModel.service_id == Service.id, isouter=True)\
    #                                   .filter(db.or_(
    #                                       Employee.name.ilike(f"%{keyword}%") if Employee else False,
    #                                       Service.name.ilike(f"%{keyword}%")
    #                                   ))

    #     orders = orders_query.order_by(Order.datetime.desc()).all()

    #     orders_by_date = {}
    #     for order in orders:
    #         order_date = order.datetime.date()
    #         if order_date not in orders_by_date:
    #             orders_by_date[order_date] = {
    #                 'date': order_date,
    #                 'total': 0.0,
    #                 'services': [],
    #                 'employee_id': None,
    #                 'promotion_id': None
    #             }

    #         order_services = OrderServiceModel.query.filter_by(order_id=order.id).all()
    #         calculated_total = 0.0
    #         for os in order_services:
    #             service = Service.query.get(os.service_id)
    #             if service:
    #                 calculated_total += service.price * os.quantity
    #                 existing_service = next(
    #                     (s for s in orders_by_date[order_date]['services'] if s['service_id'] == service.id),
    #                     None
    #                 )
    #                 if existing_service:
    #                     existing_service['quantity'] += os.quantity
    #                 else:
    #                     orders_by_date[order_date]['services'].append({
    #                         'service_id': service.id,
    #                         'name': service.name,
    #                         'quantity': os.quantity
    #                     })

    #         orders_by_date[order_date]['total'] += calculated_total
    #         if orders_by_date[order_date]['promotion_id'] is None:
    #             orders_by_date[order_date]['promotion_id'] = order.promotion_id

    #     result = list(orders_by_date.values())
    #     return result, total_days
    
    @staticmethod
    def get_revenue_by_employee_monthly(
        date_from: date = None,
        date_to: date = None,
        keyword: str = None,
        page: int = 1,
        page_size: int = 15
    ) -> Tuple[List[Dict], int]:
        """
        Retrieve monthly revenue grouped by employee.
        
        Args:
            date_from: Filter orders created on or after this date
            date_to: Filter orders created on or before this date
            keyword: Search term to filter by employee name
            page: Page number for pagination
            page_size: Number of records per page

        Returns:
            Tuple containing list of monthly revenue entries and total count
        """
        logger.debug(f"Fetching monthly revenue: date_from={date_from}, date_to={date_to}, keyword={keyword}")
        
        # Query distinct year-month-employee combinations
        query = db.session.query(
            func.extract('year', Order.datetime).label('year'),
            func.extract('month', Order.datetime).label('month'),
            Order.employee_id
        ).filter(Order.employee_id.isnot(None))  # Chỉ lấy đơn hàng có nhân viên
        
        # Apply date filters
        if date_from:
            query = query.filter(func.date(Order.datetime) >= date_from)
        if date_to:
            query = query.filter(func.date(Order.datetime) <= date_to)
        
        # Apply keyword filter
        if keyword:
            query = query.join(Employee).filter(
                Employee.name.ilike(f"%{keyword}%")
            )
        
        # Get distinct year-month-employee combinations
        distinct_query = query.distinct()
        
        # Count total records
        total_records = distinct_query.count()
        
        # Paginate
        paginated_records = distinct_query.order_by(
            func.extract('year', Order.datetime).desc(),
            func.extract('month', Order.datetime).desc(),
            Order.employee_id
        ).offset((page - 1) * page_size).limit(page_size).all()
        
        # Get detailed data for paginated records
        revenue_by_employee_monthly = {}
        
        for record in paginated_records:
            year = int(record.year)
            month = int(record.month)
            employee_id = record.employee_id
            
            if not employee_id:
                continue
                
            key = (year, month, employee_id)
            
            # Calculate start and end of month
            month_start = date(year, month, 1)
            if month == 12:
                month_end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(year, month + 1, 1) - timedelta(days=1)
            
            # Query orders for this employee in this month
            # Áp dụng lại date_from/date_to filters cho đảm bảo
            orders_query = Order.query.filter(
                Order.employee_id == employee_id,
                func.date(Order.datetime) >= month_start,
                func.date(Order.datetime) <= month_end
            )
            
            # Áp dụng date range filters nếu có
            if date_from:
                orders_query = orders_query.filter(func.date(Order.datetime) >= max(date_from, month_start))
            if date_to:
                orders_query = orders_query.filter(func.date(Order.datetime) <= min(date_to, month_end))
            
            orders = orders_query.all()
            order_count = len(orders)
            
            if order_count == 0:
                continue
                
            # Get employee info
            employee = Employee.query.get(employee_id)
            
            # Initialize result entry
            revenue_by_employee_monthly[key] = {
                'year': year,
                'month': month,
                'employee_id': employee_id,
                'employee_name': employee.name if employee else None,
                'total': 0.0,
                'order_count': order_count,
                'services': []
            }
            
            # Aggregate data from all orders
            service_totals = {}
            
            for order in orders:
                order_services = OrderServiceModel.query.filter_by(order_id=order.id).all()
                
                for os in order_services:
                    service = Service.query.get(os.service_id)
                    if service:
                        # Add to total revenue
                        service_total = service.price * os.quantity
                        revenue_by_employee_monthly[key]['total'] += service_total
                        
                        # Aggregate services
                        if service.id not in service_totals:
                            service_totals[service.id] = {
                                'service_id': service.id,
                                'name': service.name,
                                'quantity': os.quantity
                            }
                        else:
                            service_totals[service.id]['quantity'] += os.quantity
        
            # Convert aggregated services to list
            revenue_by_employee_monthly[key]['services'] = list(service_totals.values())
        
        result = list(revenue_by_employee_monthly.values())
        
        # Sort by year, month (descending) and total revenue (descending)
        result.sort(key=lambda x: (x['year'], x['month'], x['total']), reverse=True)
        
        return result, total_records