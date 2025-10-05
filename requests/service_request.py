from marshmallow import Schema, fields, validates, ValidationError

class ServiceRequestSchema(Schema):
    """
    Schema for validating service creation request parameters.
    """
    name = fields.String(required=True, validate=lambda x: len(x) <= 100)
    description = fields.String(required=False, allow_none=True)
    price = fields.Float(required=True, validate=lambda x: x >= 0)

    @validates('name')
    def validate_name(self, value, **kwargs):
        """Validate service name length and non-empty"""
        if not value or len(value.strip()) == 0:
            raise ValidationError('Name cannot be empty')
        if len(value) > 100:
            raise ValidationError('Name must not exceed 100 characters')

    @validates('price')
    def validate_price(self, value, **kwargs):
        """Validate price is non-negative"""
        if value < 0:
            raise ValidationError('Price must be non-negative')

class ServiceUpdateRequestSchema(ServiceRequestSchema):
    """
    Schema for validating service update request parameters.
    All fields are optional for update.
    """
    name = fields.String(required=False, validate=lambda x: len(x) <= 100 if x else True)
    description = fields.String(required=False, validate=lambda x: len(x) <= 255 if x else True)
    price = fields.Float(required=False, validate=lambda x: x >= 0 if x is not None else True)

class ServiceFilterRequestSchema(Schema):
    """
    Schema for validating service filter request parameters.
    """
    page = fields.Integer(load_default=1, validate=lambda x: x >= 1)
    page_size = fields.Integer(load_default=15, validate=lambda x: 1 <= x <= 100)
    keyword = fields.String(allow_none=True)  # Thêm trường keyword