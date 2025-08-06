from datetime import date
from models.employee_model import Employee
from models.order_model import Order
from models.order_service_model import OrderServiceModel
from models import db
from typing import Dict, List, Any, Tuple
import logging

from models.promotion_model import Promotion
from models.service_model import Service

logger = logging.getLogger(__name__)

class OrderService:
    """
    Service layer for handling order-related business logic.
    """
    
    @staticmethod
    def get_all_orders(
        start_date: date = None,
        end_date: date = None,
        page: int = 1,
        page_size: int = 15
    ) -> Tuple[List[Order], int]:
        """
        Retrieve orders with optional date filtering and pagination.
        
        Args:
            start_date: Filter orders created on or after this date
            end_date: Filter orders created on or before this date
            page: Page number for pagination
            page_size: Number of orders per page

        Returns:
            Tuple containing list of Order objects and total count
        """
        query = Order.query

        if start_date:
            query = query.filter(Order.created_at >= start_date)
        if end_date:
            query = query.filter(Order.created_at <= end_date)

        total_orders = query.count()
        orders = query.order_by(Order.id).offset((page - 1) * page_size).limit(page_size).all()

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
        return order

    @staticmethod
    def create_order(data: Dict[str, Any]) -> Order:
        """
        Create a new order with associated services.
        
        Args:
            data: Dictionary containing order data and services list
            
        Returns:
            Created Order object

        Raises:
            ValueError: If employee_id or promotion_id is invalid
        """
        # Extract services data
        services_data = data.pop('services', [])

        # Validate employee_id and promotion_id if provided
        if data.get('employee_id'):
            if not Employee.query.get(data['employee_id']):
                raise ValueError(f"Employee with ID {data['employee_id']} not found")
        if data.get('promotion_id'):
            if not Promotion.query.get(data['promotion_id']):
                raise ValueError(f"Promotion with ID {data['promotion_id']} not found")

        # Create order
        order = Order(**data)
        db.session.add(order)
        db.session.flush()  # Get order.id before committing

        # Create associated OrderServiceModel entries
        for service in services_data:
            order_service = OrderServiceModel(
                order_id=order.id,
                service_id=service['service_id'],
                quantity=service['quantity']
            )
            db.session.add(order_service)

        db.session.commit()
        order.services = OrderServiceModel.query.filter_by(order_id=order.id).all()
        return order

    @staticmethod
    def update_order(order_id: int, data: Dict[str, Any]) -> Order:
        """
        Update an existing order and its associated services.
        
        Args:
            order_id: ID of the order to update
            data: Dictionary containing updated order data and optional services list
            
        Returns:
            Updated Order object

        Raises:
            ValueError: If order or referenced IDs not found
        """
        order = Order.query.get(order_id)
        if not order:
            raise ValueError(f"Order with ID {order_id} not found")

        # Extract services data if provided
        services_data = data.pop('services', None)

        # Validate employee_id and promotion_id if provided
        if 'employee_id' in data and data['employee_id']:
            if not Employee.query.get(data['employee_id']):
                raise ValueError(f"Employee with ID {data['employee_id']} not found")
        if 'promotion_id' in data and data['promotion_id']:
            if not Promotion.query.get(data['promotion_id']):
                raise ValueError(f"Promotion with ID {data['promotion_id']} not found")

        # Update order fields
        for key, value in data.items():
            setattr(order, key, value)

        # Update services if provided
        if services_data is not None:
            # Delete existing services
            OrderServiceModel.query.filter_by(order_id=order_id).delete()
            # Add new services
            for service in services_data:
                order_service = OrderServiceModel(
                    order_id=order_id,
                    service_id=service['service_id'],
                    quantity=service['quantity']
                )
                db.session.add(order_service)

        db.session.commit()
        order.services = OrderServiceModel.query.filter_by(order_id=order_id).all()
        return order

    @staticmethod
    def delete_order(order_id: int) -> None:
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