from flask import Blueprint, request, jsonify
from services.dashboard_service import DashboardService
from requests.dashboard_request import DashboardRequestSchema
from responses.dashboard_response import DashboardResponseSchema
from utils.logger import logger
from typing import Tuple, Dict, Any
from http import HTTPStatus
from helpers.format_response import format_response

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/v1/dashboard')

request_schema = DashboardRequestSchema()
response_schema = DashboardResponseSchema()

@dashboard_bp.route('/', methods=['GET'])
def get_dashboard_data() -> Tuple[Dict, int]:
    """
    Retrieve dashboard data for the specified or current month/year.
    
    Returns:
        Formatted response with dashboard data
    """
    try:
        params = request.args.to_dict()
        logger.info(f"Received parameters: {params}")
        
        errors = request_schema.validate(params)
        if errors:
            logger.warning(f"Validation error in get_dashboard_data: {errors}")
            return format_response(
                data=errors,
                message="Validation error",
                status=HTTPStatus.BAD_REQUEST
            )

        dashboard_data = DashboardService.get_dashboard_data(
            month=params.get('month'),
            year=params.get('year')
        )
        
        return format_response(
            data=response_schema.dump(dashboard_data),
            message="Dashboard data retrieved successfully",
            status=HTTPStatus.OK
        )
    except Exception as e:
        logger.error(f"Error retrieving dashboard data: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )