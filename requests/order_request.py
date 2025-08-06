from marshmallow import Schema, fields, validates, ValidationError
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
    start_date = fields.Date(allow_none=True)
    end_date = fields.Date(allow_none=True)
    page = fields.Integer(load_default=1, validate=lambda x: x >= 1)
    page_size = fields.Integer(load_default=15, validate=lambda x: 1 <= x <= 100)

    @validates('end_date')
    def validate_end_date(self, value, **kwargs):
        """Ensure end_date is not before start_date"""
        if 'start_date' in self.context and self.context['start_date'] and value:
            if value < self.context['start_date']:
                raise ValidationError('end_date must not be before start_date')