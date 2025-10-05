from flask import Blueprint, jsonify
from http import HTTPStatus
from typing import Dict, Tuple
from helpers.format_response import format_response
from utils.logger import logger
from datetime import datetime

health_bp = Blueprint('health', __name__, url_prefix='/api/v1/health')

@health_bp.route('/', methods=['GET'])
def check_health() -> Tuple[Dict, int]:
    """
    Check the health status of the server.
    
    Returns:
        Formatted response with health status
    """
    try:
        return format_response(
            data={
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat()
            },
            message="Server is healthy",
            status=HTTPStatus.OK
        )
    except Exception as e:
        logger.error(f"Error checking health: {str(e)}")
        return format_response(
            message="Internal server error",
            status=HTTPStatus.INTERNAL_SERVER_ERROR
        )