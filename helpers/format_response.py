from http import HTTPStatus
from typing import Any, Dict, Tuple
from flask import jsonify


def format_response(data: Any = None, message: str = "Success", status: int = HTTPStatus.OK) -> Tuple[Dict, int]:
    """
    Format API response in a standardized way.
    
    Args:
        data: Response data to be included
        message: Response message
        status: HTTP status code
    
    Returns:
        Tuple containing response dictionary and status code
    """
    response = {
        "data": data,
        "message": message,
        "status": status
    }
    return jsonify(response), status