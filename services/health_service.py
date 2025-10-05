from datetime import datetime
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class HealthService:
    """
    Service layer for handling health check logic.
    """

    @staticmethod
    def check_health() -> Dict:
        """
        Check the health status of the server.
        
        Returns:
            Dictionary containing health status and timestamp
        """
        try:
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking health: {str(e)}")
            raise