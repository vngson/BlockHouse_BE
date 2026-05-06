from datetime import date
from flask import Blueprint, request, jsonify
from helpers.format_response import format_response
from models.order_model import Order
from models import db
from requests.order_request import OrderByDateAndEmployeeRequest, OrderCreateRequest, OrderOneDateRequest, OrderUpdateRequest, OrderFilterRequest
from responses.order_response import OrderResponseSchema, OrdersByDateResponseSchema, OrdersForOneDateResponseSchema, RevenueByEmployeeMonthlyResponseSchema, RevenueByEmployeeResponseSchema
from services.order_service import OrderService
from settings import PAGE_SIZE
from utils.logger import logger
from typing import Tuple, Dict, Any
from http import HTTPStatus

order_bp = Blueprint('order', __name__, url_prefix='/api/v1/orders')

request_create_schema = OrderCreateRequest()
request_update_schema = OrderUpdateRequest()
request_filter_schema = OrderFilterRequest()
request_one_date_schema = OrderOneDateRequest()
request_date_employee_schema = OrderByDateAndEmployeeRequest()
response_schema = OrderResponseSchema()
response_many_schema = OrderResponseSchema(many=True)
response_monthly_revenue_schema = RevenueByEmployeeMonthlyResponseSchema(many=True)

@order_bp.route('/', methods=['POST'])
def get_all_orders() -> Tuple[Dict, int]:
    """
    Retrieve all orders with optional filters, date range, keyword search, and pagination.
    
    Returns:
        Formatted response with list of orders, pagination info, and total count
    """
    try:
        data = request.get_json() or {}
        errors = request_filter_schema.validate(data)
        if errors:
            logger.warning(f"Validation error in get_all_orders: {errors}")
            return format_response(
                data=errors,
                message="Validation error",
                status=HTTPStatus.BAD_REQUEST
            )

        page = data.get('page', 1)
        page_size = data.get('page_size', PAGE_SIZE)
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        keyword = data.get('keyword')

        orders, total_orders = OrderService.get_all_orders(
            date_from=date_from,
            date_to=date_to,
            keyword=keyword,
            page=page,
            page_size=page_size
        )
        
        return format_response(
            data={
                'orders': response_many_schema.dump(orders),
                'page': page,
                'page_size': page_size,
                'total_orders': total_orders
            },
            message="Orders retrieved successfully",
            status=HTTPStatus.OK
        )
    except Exception as e:
        logger.error(f"Error retrieving orders: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )
    
@order_bp.route('/by_date', methods=['POST'])
def get_orders_by_date() -> Tuple[Dict, int]:
    """
    Retrieve all orders grouped by date, excluding id and employee_name, with optional date range and keyword search.
    
    Returns:
        Formatted response with list of orders grouped by date, pagination info, and total count of days
    """
    try:
        # Handle empty request body case
        if not request.data:
            data = {}
        else:
            data = request.get_json(silent=True) or {}
        
        # Set context for schema validation
        request_filter_schema.context = data
        
        # Load data to ensure date fields are converted to datetime.date
        validated_data = request_filter_schema.load(data)
        
        page = validated_data.get('page', 1)
        page_size = validated_data.get('page_size', PAGE_SIZE)
        date_from = validated_data.get('date_from')
        date_to = validated_data.get('date_to')
        keyword = validated_data.get('keyword')

        # Call service to get orders grouped by date
        date_orders, total_days = OrderService.get_orders_by_date(
            date_from=date_from,
            date_to=date_to,
            keyword=keyword,
            page=page,
            page_size=page_size
        )
        
        # Use schema for serialization
        orders_by_date_schema = OrdersByDateResponseSchema(many=True)
        
        return format_response(
            data={
                'orders_by_date': orders_by_date_schema.dump(date_orders),
                'page': page,
                'page_size': page_size,
                'total_days': total_days
            },
            message="Orders retrieved successfully",
            status=HTTPStatus.OK
        )
    except ValueError as ve:
        logger.warning(f"Validation error in get_orders_by_date: {str(ve)}")
        return format_response(
            message=str(ve),
            status=HTTPStatus.BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error retrieving orders by date: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

@order_bp.route('/revenue_by_employee', methods=['POST'])
def get_revenue_by_employee() -> Tuple[Dict, int]:
    try:
        if not request.data:
            data = {}
        else:
            data = request.get_json(silent=True) or {}
        logger.debug(f"Yêu cầu thô: {data}")
        request_filter_schema.context = data
        validated_data = request_filter_schema.load(data)
        logger.debug(f"Dữ liệu đã deserialize: {validated_data}")
        
        page = validated_data.get('page', 1)
        page_size = validated_data.get('page_size', PAGE_SIZE)
        date_from = validated_data.get('date_from')
        date_to = validated_data.get('date_to')
        keyword = validated_data.get('keyword')

        print(f"Validated data: {validated_data}")  # Debug log

        # Call service to get revenue grouped by date and employee
        revenue_data, total_date_employees = OrderService.get_revenue_by_employee(
            date_from=date_from,
            date_to=date_to,
            keyword=keyword,
            page=page,
            page_size=page_size
        )
        
        # Use schema for serialization
        revenue_schema = RevenueByEmployeeResponseSchema(many=True)
        
        return format_response(
            data={
                'revenue_by_employee': revenue_schema.dump(revenue_data),
                'page': page,
                'page_size': page_size,
                'total_date_employees': total_date_employees
            },
            message="Revenue by employee retrieved successfully",
            status=HTTPStatus.OK
        )
    except ValueError as ve:
        logger.warning(f"Validation error in get_revenue_by_employee: {str(ve)}")
        return format_response(
            message=str(ve),
            status=HTTPStatus.BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error retrieving revenue by employee: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )    

@order_bp.route('/for_one_date', methods=['POST'])
def get_orders_for_one_date() -> Tuple[Dict, int]:
    """
    Retrieve all orders for a specific date, grouped and combined into one entry.
    
    Request body:
        {
            "order_date": "2025-09-20"
        }

    Returns:
        Formatted response with list of orders for the date and total count of orders
    """
    try:
        # Handle empty body
        if not request.data:
            data = {}
        else:
            data = request.get_json(silent=True) or {}

        # Set context for schema validation
        request_one_date_schema.context = data
        
        # Load data to ensure date fields are converted to datetime.date
        validated_data = request_one_date_schema.load(data)

        # Get order_date from body
        order_date = validated_data.get("order_date")

        # Call service
        date_orders, total_orders = OrderService.get_orders_for_one_date(order_date)

        # Schema serialize
        orders_by_date_schema = OrdersForOneDateResponseSchema(many=True)

        return format_response(
            data={
                "orders_by_date": orders_by_date_schema.dump(date_orders),
                "order_date": order_date.isoformat(),
                "total_orders": total_orders
            },
            message="Orders retrieved successfully",
            status=HTTPStatus.OK
        )

    except ValueError as ve:
        logger.warning(f"Validation error in get_orders_for_one_date: {str(ve)}")
        return format_response(
            message=str(ve),
            status=HTTPStatus.BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error retrieving orders for one date: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )
    
@order_bp.route('/by_date_and_employee', methods=['POST'])
def get_orders_by_date_and_employee() -> Tuple[Dict, int]:
    """
    Retrieve all orders for a specific date and employee ID.
    
    Returns:
        Formatted response with order details for the specified date and employee
    """
    try:
        if not request.data:
            data = {}
        else:
            data = request.get_json(silent=True) or {}
        
        # Set context for schema validation
        request_date_employee_schema.context = data
        
        # Load and validate data
        validated_data = request_date_employee_schema.load(data)
        
        order_date = validated_data.get('order_date')
        employee_id = validated_data.get('employee_id')
        
        # Call service to get orders for the specific date and employee
        order_data, total_orders = OrderService.get_orders_by_date_and_employee(
            order_date=order_date,
            employee_id=employee_id
        )
        
        # Use schema for serialization
        revenue_by_employee_schema = RevenueByEmployeeResponseSchema()
        
        return format_response(
            data={
                'order_data': revenue_by_employee_schema.dump(order_data),
                'total_orders': total_orders
            },
            message="Orders for date and employee retrieved successfully",
            status=HTTPStatus.OK
        )
    except ValueError as ve:
        logger.warning(f"Validation error in get_orders_by_date_and_employee: {str(ve)}")
        return format_response(
            message=str(ve),
            status=HTTPStatus.BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error retrieving orders by date and employee: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

@order_bp.route('/create', methods=['POST'])
def create_order() -> Tuple[Dict, int]:
    try:
        data = request.get_json()
        logger.info(f"Received request data: {data}")  # Log raw input
        errors = request_create_schema.validate(data)
        if errors:
            logger.warning(f"Validation error in create_order: {errors}")
            return format_response(
                data=errors,
                message="Validation error",
                status=HTTPStatus.BAD_REQUEST
            )

        validated_data = request_create_schema.load(data)  # Deserialize data
        logger.info(f"Validated data: {validated_data}")  # Log validated data
        order = OrderService.create_order(validated_data)
        return format_response(
            data=response_schema.dump(order),
            message="Order created successfully",
            status=HTTPStatus.CREATED
        )
    except ValueError as e:
        logger.warning(f"Validation error in create_order: {str(e)}")
        return format_response(
            message=str(e),
            status=HTTPStatus.BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

@order_bp.route('/<int:order_id>', methods=['GET'])
def get_order(order_id: int) -> Tuple[Dict, int]:
    """
    Retrieve a specific order by ID.
    
    Args:
        order_id: ID of the order to retrieve
    
    Returns:
        Formatted response with order data
    """
    try:
        order = OrderService.get_order(order_id)
        return format_response(
            data=response_schema.dump(order),
            message="Order retrieved successfully",
            status=HTTPStatus.OK
        )
    except ValueError as e:
        logger.warning(f"Order not found: {order_id}")
        return format_response(
            message=str(e),
            status=HTTPStatus.NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error retrieving order {order_id}: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

@order_bp.route('/<int:order_id>', methods=['PUT'])
def update_order(order_id: int) -> Tuple[Dict, int]:
    """
    Update an existing order.
    
    Args:
        order_id: ID of the order to update
    
    Returns:
        Formatted response with updated order data
    """
    try:
        data = request.get_json()
        errors = request_update_schema.validate(data)
        if errors:
            logger.warning(f"Validation error in update_order: {errors}")
            return format_response(
                data=errors,
                message="Validation error",
                status=HTTPStatus.BAD_REQUEST
            )

        order = OrderService.update_order(order_id, data)
        return format_response(
            data=response_schema.dump(order),
            message="Order updated successfully",
            status=HTTPStatus.OK
        )
    except ValueError as e:
        logger.warning(f"Order not found: {order_id}")
        return format_response(
            message=str(e),
            status=HTTPStatus.NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error updating order {order_id}: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

@order_bp.route('/<int:order_id>', methods=['DELETE'])
def delete_order(order_id: int) -> Tuple[Dict, int]:
    """
    Delete an order.
    
    Args:
        order_id: ID of the order to delete
    
    Returns:
        Formatted response indicating deletion success
    """
    try:
        OrderService.delete_order(order_id)
        return format_response(
            message="Order deleted successfully",
            data=None,
            status=HTTPStatus.OK
        )
    except ValueError as e:
        logger.warning(f"Order not found: {order_id}")
        return format_response(
            message=str(e),
            data=None,
            status=HTTPStatus.NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error deleting order {order_id}: {str(e)}")
        return format_response(
            message="Internal server error",
            data=None,
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )
    
@order_bp.route('/revenue_monthly_by_employee', methods=['POST'])
def get_revenue_monthly_by_employee() -> Tuple[Dict, int]:
    """
    Retrieve monthly revenue grouped by employee with same interface as other APIs.
    
    Request body (example):
        {
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
            "keyword": "search term",
            "page": 1,
            "page_size": 15
        }

    Returns:
        Formatted response with monthly revenue by employee
    """
    try:
        # Handle empty request body case
        if not request.data:
            data = {}
        else:
            data = request.get_json(silent=True) or {}
        
        # Set context for schema validation
        request_filter_schema.context = data
        
        # Load data to ensure date fields are converted to datetime.date
        validated_data = request_filter_schema.load(data)
        
        page = validated_data.get('page', 1)
        page_size = validated_data.get('page_size', PAGE_SIZE)
        date_from = validated_data.get('date_from')
        date_to = validated_data.get('date_to')
        keyword = validated_data.get('keyword')

        # Call service to get monthly revenue by employee
        monthly_revenue_data, total_records = OrderService.get_revenue_by_employee_monthly(
            date_from=date_from,
            date_to=date_to,
            keyword=keyword,
            page=page,
            page_size=page_size
        )
        
        return format_response(
            data={
                'revenue_monthly_by_employee': response_monthly_revenue_schema.dump(monthly_revenue_data),
                'date_from': date_from.isoformat() if date_from else None,
                'date_to': date_to.isoformat() if date_to else None,
                'page': page,
                'page_size': page_size,
                'total_records': total_records
            },
            message="Monthly revenue by employee retrieved successfully",
            status=HTTPStatus.OK
        )
        
    except ValueError as ve:
        logger.warning(f"Validation error in get_revenue_monthly_by_employee: {str(ve)}")
        return format_response(
            message=str(ve),
            status=HTTPStatus.BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error retrieving monthly revenue by employee: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )