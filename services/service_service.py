from models import db
from models.service_model import Service
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import logging
from sqlalchemy import or_

logger = logging.getLogger(__name__)

class ServiceService:
    """
    Service layer for handling service-related business logic.
    """

    @staticmethod
    def get_all_services(page: int = 1, page_size: int = 15, keyword: str = None) -> Tuple[List[Service], int]:
        """
        Retrieve all services with pagination.
        
        Args:
            page: Page number for pagination
            page_size: Number of services per page
            keyword: Optional keyword to search in name and description
        
        Returns:
            Tuple containing list of service objects and total count
        """
        try:
            query = db.session.query(Service)
            
            if keyword:
                query = query.filter(or_(
                    Service.name.ilike(f"%{keyword}%"),
                    Service.description.ilike(f"%{keyword}%")
                ))
                
            total_services = query.count()
            services = query.order_by(Service.name.asc()).offset((page - 1) * page_size).limit(page_size).all()
            return services, total_services
        except Exception as e:
            logger.error(f"Error retrieving all services: {str(e)}")
            raise

    @staticmethod
    def get_all_services_no_pagination() -> List[Service]:
        """
        Retrieve all services without pagination.
        
        Returns:
            List of all service objects
        """
        try:
            services = db.session.query(Service).order_by(Service.name.asc()).all()
            return services
        except Exception as e:
            logger.error(f"Error retrieving all services without pagination: {str(e)}")
            raise
                
    @staticmethod
    def get_service_by_id(service_id: int) -> Optional[Service]:
        """
        Retrieve a service by its ID.
        
        Args:
            service_id: ID of the service to retrieve
        
        Returns:
            Service object or None if not found
        """
        try:
            return db.session.query(Service).filter_by(id=service_id).first()
        except Exception as e:
            logger.error(f"Error retrieving service {service_id}: {str(e)}")
            raise

    @staticmethod
    def check_service_name_exists(name: str, exclude_service_id: Optional[int] = None) -> bool:
        """
        Check if a service name already exists in the database.
        
        Args:
            name: Service name to check
            exclude_service_id: Optional ID to exclude (used during update)
        
        Returns:
            True if name exists, False otherwise
        """
        try:
            query = db.session.query(Service).filter(Service.name.ilike(name))
            if exclude_service_id:
                query = query.filter(Service.id != exclude_service_id)
            return query.first() is not None
        except Exception as e:
            logger.error(f"Error checking service name existence: {str(e)}")
            raise

    @staticmethod
    def create_service(data: Dict[str, Any]) -> Service:
        """
        Create a new service.
        
        Args:
            data: Dictionary containing service data (name, description, price)
        
        Returns:
            Created service object
        """
        try:
            # Check if service name already exists
            if ServiceService.check_service_name_exists(data['name']):
                    raise ValueError("Dịch vụ này đã tồn tại")
            
            # Convert null description to empty string
            description = data.get('description', '') or ''
            
            service = Service(
                name=data['name'],
                description=description,
                price=data['price']
            )
            db.session.add(service)
            db.session.commit()
            return service
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating service: {str(e)}")
            raise

    @staticmethod
    def update_service(service_id: int, data: Dict[str, Any]) -> Optional[Service]:
        """
        Update an existing service.
        
        Args:
            service_id: ID of the service to update
            data: Dictionary containing updated service data
        
        Returns:
            Updated service object or None if not found
        """
        try:
            service = db.session.query(Service).filter_by(id=service_id).first()
            if not service:
                return None
            
            if 'name' in data and data['name']:
                # Check if new name already exists (excluding current service)
                if ServiceService.check_service_name_exists(data['name'], service_id):
                    raise ValueError("Dịch vụ này đã tồn tại")
                service.name = data['name']
            
            if 'description' in data:
                # Convert null description to empty string
                service.description = data['description'] or ''
                
            if 'price' in data and data['price'] is not None:
                service.price = data['price']
            
            db.session.commit()
            return service
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating service {service_id}: {str(e)}")
            raise