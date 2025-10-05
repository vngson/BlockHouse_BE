import datetime
from marshmallow import Schema, fields, validates, ValidationError, validates_schema
import datetime
from datetime import date

class OrderServiceRequest(Schema):
    """
    Schema for validating order service data (for OrderServiceModel).
    """
    service_id = fields.Integer(required=True, validate=lambda x: x > 0)
    quantity = fields.Integer(required=True, validate=lambda x: x >= 1)

class OrderCreateRequest(Schema):
    """
    Schema for validating order creation request data.
    """
    datetime = fields.DateTime(required=True)
    employee_id = fields.Int(required=False, allow_none=True)
    promotion_id = fields.Int(required=False, allow_none=True)
    total = fields.Float(required=False, allow_none=True)
    services = fields.List(fields.Nested(OrderServiceRequest), required=True, validate=lambda x: len(x) > 0)

    @validates('datetime')
    def validate_datetime(self, value, **kwargs):
        """
        Validate that the datetime is a valid datetime object and not in the future.
        """
        if not isinstance(value, datetime.datetime):
            raise ValidationError(f"Expected datetime object, got {type(value)}")
        if value.date() > date.today():
            raise ValidationError("Order datetime must not be in the future")
        return value

    @validates('services')
    def validate_services(self, value, **kwargs):
        """Ensure services list is not empty and contains valid service_id and quantity"""
        if not value:
            raise ValidationError('Services list cannot be empty')

class OrderUpdateRequest(Schema):
    """
    Schema for validating order update request data.
    """
    datetime = fields.DateTime(required=False)
    employee_id = fields.Int(required=False, allow_none=True)
    promotion_id = fields.Int(required=False, allow_none=True)
    total = fields.Float(required=False, allow_none=True)
    services = fields.List(fields.Nested(OrderServiceRequest), required=False)

class OrderFilterRequest(Schema):
    """
    Schema for validating order filter request data.
    """
    date_from = fields.Date(allow_none=True)
    date_to = fields.Date(allow_none=True)
    keyword = fields.String(allow_none=True)
    page = fields.Integer(load_default=1, validate=lambda x: x >= 1)
    page_size = fields.Integer(load_default=15, validate=lambda x: 1 <= x <= 100)

    @validates_schema
    def validate_dates(self, data, **kwargs):
        """Ensure date_to is not before date_from"""
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        if date_from and date_to and date_to < date_from:
            raise ValidationError({'date_to': ['date_to must not be before date_from']})

class OrderOneDateRequest(Schema):
    """
    Schema for validating order filter request data.
    """
    order_date = fields.Date(allow_none=True)

    @validates('order_date')
    def validate_order_date(self, value, **kwargs):
        """Ensure order_date is not in the future"""
        if value and value > date.today():
            raise ValidationError('order_date must not be in the future')
        
class OrderByDateAndEmployeeRequest(Schema):
    """
    Schema for validating request data for orders by date and employee ID.
    """
    order_date = fields.Date(required=True)
    employee_id = fields.Integer(required=True, validate=lambda x: x > 0)

    @validates('order_date')
    def validate_order_date(self, value, **kwargs):
        """Ensure order_date is not in the future"""
        if value > date.today():
            raise ValidationError('order_date must not be in the future')