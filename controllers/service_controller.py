# [file name]: service_controller.py
# [file content begin]
from flask import Blueprint, request, jsonify
from services.service_service import ServiceService
from requests.service_request import ServiceRequestSchema, ServiceUpdateRequestSchema, ServiceFilterRequestSchema
from responses.service_response import ServiceResponseSchema, ServiceListResponseSchema
from utils.logger import logger
from typing import Tuple, Dict, Any
from http import HTTPStatus
from helpers.format_response import format_response
from settings import PAGE_SIZE

service_bp = Blueprint('service', __name__, url_prefix='/api/v1/service')

request_schema = ServiceRequestSchema()
update_request_schema = ServiceUpdateRequestSchema()
filter_request_schema = ServiceFilterRequestSchema()
response_schema = ServiceResponseSchema()
list_response_schema = ServiceResponseSchema(many=True)

@service_bp.route('/', methods=['GET'])
def get_all_services() -> Tuple[Dict, int]:
    """
    Retrieve all services with optional pagination and keyword search.
    
    Returns:
        Formatted response with list of services, pagination info, and total count
    """
    try:
        data = request.get_json(silent=True) or {}
        if not data:
            data = {
                'page': request.args.get('page', 1),
                'page_size': request.args.get('page_size', PAGE_SIZE),
                'keyword': request.args.get('keyword'),
            }

        errors = filter_request_schema.validate(data)
        if errors:
            logger.warning(f"Validation error in get_all_services: {errors}")
            return format_response(
                data=errors,
                message="Validation error",
                status=HTTPStatus.BAD_REQUEST
            )

        page = int(data.get('page', 1) or 1)
        page_size = int(data.get('page_size', PAGE_SIZE) or PAGE_SIZE)
        keyword = data.get('keyword')

        services, total_services = ServiceService.get_all_services(
            page=page,
            page_size=page_size,
            keyword=keyword
        )
        return format_response(
            data={
                'services': list_response_schema.dump(services),
                'page': page,
                'page_size': page_size,
                'total_services': total_services
            },
            message="Services retrieved successfully",
            status=HTTPStatus.OK
        )
    except Exception as e:
        logger.error(f"Error retrieving services: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

@service_bp.route('/all', methods=['GET'])
def get_all_services_no_pagination() -> Tuple[Dict, int]:
    """
    Retrieve all services without pagination.
    
    Returns:
        Formatted response with list of all services
    """
    try:
        services = ServiceService.get_all_services_no_pagination()
        return format_response(
            data={
                'services': list_response_schema.dump(services)
            },
            message="All services retrieved successfully",
            status=HTTPStatus.OK
        )
    except Exception as e:
        logger.error(f"Error retrieving all services without pagination: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

@service_bp.route('/<int:service_id>', methods=['GET'])
def get_service_by_id(service_id: int) -> Tuple[Dict, int]:
    """
    Retrieve a single service by ID.
    
    Args:
        service_id: ID of the service to retrieve
    
    Returns:
        Formatted response with service data
    """
    try:
        service = ServiceService.get_service_by_id(service_id)
        if not service:
            return format_response(
                message="Service not found",
                status=HTTPStatus.NOT_FOUND
            )
        return format_response(
            data=response_schema.dump(service),
            message="Service retrieved successfully",
            status=HTTPStatus.OK
        )
    except Exception as e:
        logger.error(f"Error retrieving service {service_id}: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

@service_bp.route('/', methods=['POST'])
def create_service() -> Tuple[Dict, int]:
    """
    Create a new service.
    
    Returns:
        Formatted response with created service data
    """
    try:
        data = request.get_json()
        errors = request_schema.validate(data)
        if errors:
            logger.warning(f"Validation error in create_service: {errors}")
            return format_response(
                data=errors,
                message="Validation error",
                status=HTTPStatus.BAD_REQUEST
            )

        service = ServiceService.create_service(data)
        return format_response(
            data=response_schema.dump(service),
            message="Service created successfully",
            status=HTTPStatus.CREATED
        )
    except Exception as e:
        logger.error(f"Error creating service: {str(e)}")
        return format_response(
            message=f"{str(e)}",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

@service_bp.route('/<int:service_id>', methods=['PUT'])
def update_service(service_id: int) -> Tuple[Dict, int]:
    """
    Update an existing service.
    
    Args:
        service_id: ID of the service to update
    
    Returns:
        Formatted response with updated service data
    """
    try:
        data = request.get_json()
        errors = update_request_schema.validate(data)
        if errors:
            logger.warning(f"Validation error in update_service: {errors}")
            return format_response(
                data=errors,
                message="Validation error",
                status=HTTPStatus.BAD_REQUEST
            )

        service = ServiceService.update_service(service_id, data)
        if not service:
            return format_response(
                message="Service not found",
                status=HTTPStatus.NOT_FOUND
            )
        return format_response(
            data=response_schema.dump(service),
            message="Service updated successfully",
            status=HTTPStatus.OK
        )
    except Exception as e:
        logger.error(f"Error updating service {service_id}: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )
# [file content end]