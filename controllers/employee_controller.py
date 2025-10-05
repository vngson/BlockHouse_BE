from flask import Blueprint, request, jsonify
from helpers.format_response import format_response
from models.employee_model import Employee
from models import db
from requests.employee_request import EmployeeFilterRequestSchema, EmployeeRequestSchema, EmployeeRequestUpdateSchema
from responses.employee_response import EmployeeResponseSchema
from services.employee_service import EmployeeService
from settings import PAGE_SIZE
from utils.logger import logger
from typing import Tuple, Dict, Any
from http import HTTPStatus

employee_bp = Blueprint('employee', __name__, url_prefix='/api/v1/employees')

request_update_schema = EmployeeRequestUpdateSchema()
request_schema = EmployeeRequestSchema()
request_filter_schema = EmployeeFilterRequestSchema()
response_schema = EmployeeResponseSchema()
response_many_schema = EmployeeResponseSchema(many=True)

@employee_bp.route('/', methods=['POST'])
def get_all_employees() -> Tuple[Dict, int]:
    """
    Retrieve all employees.
    
    Returns:
        Formatted response with list of employees
    """
    try:
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

        employees, total_employees = EmployeeService.get_all_employees(
            start_date=date_from,
            end_date=date_to,
            page=page,
            page_size=PAGE_SIZE,
            keyword=keyword
        )
        
        return format_response(
            data={
                'employees': response_many_schema.dump(employees),
                'page': page,
                'page_size': PAGE_SIZE,
                'total_employees': total_employees
            },
            message="Employees retrieved successfully",
            status=HTTPStatus.OK
        )
    except Exception as e:
        logger.error(f"Error retrieving employees: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

@employee_bp.route('/<int:employee_id>', methods=['GET'])
def get_employee(employee_id: int) -> Tuple[Dict, int]:
    """
    Retrieve a specific employee by ID.
    
    Args:
        employee_id: ID of the employee to retrieve
    
    Returns:
        Formatted response with employee data
    """
    try:
        employee = EmployeeService.get_employee(employee_id)
        return format_response(
            data=response_schema.dump(employee),
            message="Employee retrieved successfully",
            status=HTTPStatus.OK
        )
    except ValueError as e:
        logger.warning(f"Employee not found: {employee_id}")
        return format_response(
            message=str(e),
            status=HTTPStatus.NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error retrieving employee {employee_id}: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

@employee_bp.route('/create_employee', methods=['POST'])
def create_employee() -> Tuple[Dict, int]:
    """
    Create a new employee with default status=1 if not provided.
    
    Returns:
        Formatted response with created employee data
    """
    try:
        data = request.get_json()
        data.setdefault('status', 1)  # Set default status to 1 (active)
        errors = request_schema.validate(data)
        if errors:
            logger.warning(f"Validation error in create_employee: {errors}")
            return format_response(
                data=errors,
                message="Validation error",
                status=HTTPStatus.BAD_REQUEST
            )

        employee = EmployeeService.create_employee(data)
        return format_response(
            data=response_schema.dump(employee),
            message="Employee created successfully",
            status=HTTPStatus.CREATED
        )
    except Exception as e:
        logger.error(f"Error creating employee: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

@employee_bp.route('/<int:employee_id>', methods=['PUT'])
def update_employee(employee_id: int) -> Tuple[Dict, int]:
    """
    Update an existing employee.
    
    Args:
        employee_id: ID of the employee to update
    
    Returns:
        Formatted response with updated employee data
    """
    try:
        data = request.get_json()
        errors = request_update_schema.validate(data)
        if errors:
            logger.warning(f"Validation error in update_employee: {errors}")
            return format_response(
                data=errors,
                message="Validation error",
                status=HTTPStatus.BAD_REQUEST
            )

        employee = EmployeeService.update_employee(employee_id, data)
        return format_response(
            data=response_schema.dump(employee),
            message="Employee updated successfully",
            status=HTTPStatus.OK
        )
    except ValueError as e:
        logger.warning(f"Employee not found: {employee_id}")
        return format_response(
            message=str(e),
            status=HTTPStatus.NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error updating employee {employee_id}: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

@employee_bp.route('/<int:employee_id>', methods=['DELETE'])
def delete_employee(employee_id: int) -> Tuple[Dict, int]:
    """
    Delete an employee.
    
    Args:
        employee_id: ID of the employee to delete
    
    Returns:
        Formatted response indicating deletion success
    """
    try:
        EmployeeService.delete_employee(employee_id)
        return format_response(
            message="Employee deleted successfully",
            status=HTTPStatus.OK
        )
    except ValueError as e:
        logger.warning(f"Employee not found: {employee_id}")
        return format_response(
            message=str(e),
            status=HTTPStatus.NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error deleting employee {employee_id}: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )