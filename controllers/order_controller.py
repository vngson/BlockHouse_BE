from flask import Blueprint, request, jsonify
from helpers.format_response import format_response
from models.order_model import Order
from models import db
from requests.order_request import OrderCreateRequest, OrderUpdateRequest, OrderFilterRequest
from responses.order_response import OrderResponseSchema
from services.order_service import OrderService
from settings import PAGE_SIZE
from utils.logger import logger
from typing import Tuple, Dict, Any
from http import HTTPStatus

order_bp = Blueprint('order', __name__, url_prefix='/api/v1/orders')

request_create_schema = OrderCreateRequest()
request_update_schema = OrderUpdateRequest()
request_filter_schema = OrderFilterRequest()
response_schema = OrderResponseSchema()
response_many_schema = OrderResponseSchema(many=True)

@order_bp.route('/', methods=['POST'])
def get_all_orders() -> Tuple[Dict, int]:
    """
    Retrieve all orders with optional filters and pagination.
    
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
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        orders, total_orders = OrderService.get_all_orders(
            start_date=start_date,
            end_date=end_date,
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

@order_bp.route('/create', methods=['POST'])
def create_order() -> Tuple[Dict, int]:
    """
    Create a new order with associated services.
    
    Returns:
        Formatted response with created order data
    """
    try:
        data = request.get_json()
        errors = request_create_schema.validate(data)
        if errors:
            logger.warning(f"Validation error in create_order: {errors}")
            return format_response(
                data=errors,
                message="Validation error",
                status=HTTPStatus.BAD_REQUEST
            )

        order = OrderService.create_order(data)
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
            status=HTTPStatus.OK
        )
    except ValueError as e:
        logger.warning(f"Order not found: {order_id}")
        return format_response(
            message=str(e),
            status=HTTPStatus.NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error deleting order {order_id}: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )