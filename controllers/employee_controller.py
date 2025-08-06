from flask import Blueprint, request, jsonify
from helpers.format_response import format_response
from models.employee_model import Employee
from models import db
from requests.employee_request import EmployeeRequestSchema
from responses.employee_response import EmployeeResponseSchema
from services.employee_service import EmployeeService
from settings import PAGE_SIZE
from utils.logger import logger
from typing import Tuple, Dict, Any
from http import HTTPStatus

employee_bp = Blueprint('employee', __name__, url_prefix='/api/v1/employees')

request_schema = EmployeeRequestSchema()
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
        data = request.get_json() or {}
        errors = request_schema.validate(data)
        if errors:
            logger.warning(f"Validation error in get_all_employees: {errors}")
            return format_response(
                data=errors,
                message="Validation error",
                status=HTTPStatus.BAD_REQUEST
            )

        page = data.get('page', 1)
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        employees, total_employees = EmployeeService.get_all_employees(
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=PAGE_SIZE
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
        errors = request_schema.validate(data)
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