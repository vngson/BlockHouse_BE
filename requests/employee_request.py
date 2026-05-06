from marshmallow import Schema, fields, validates, validates_schema, ValidationError
import re

class EmployeeRequestUpdateSchema(Schema):
    """
    Schema for validating employee status update only.
    """
    status = fields.Integer(required=True)

    @validates('status')
    def validate_status(self, value, **kwargs):
        """Validate status is either 0 or 1"""
        if value not in [0, 1]:
            raise ValidationError('Status must be 0 (inactive) or 1 (active)')

class EmployeeRequestSchema(Schema): 
    """ Schema for validating employee request data. """ 
    name = fields.String(required=True, validate=lambda x: len(x.strip()) > 0) 
    phone = fields.String(allow_none=True) 
    status = fields.Integer(allow_none=True) 

    @validates('phone')
    def validate_phone(self, value, **kwargs):
        """Validate phone number format"""
        if value and not re.match(r'^\+?1?\d{9,15}$', value):
            raise ValidationError('Invalid phone number format')

class EmployeeFilterRequestSchema(Schema):
    """
    Schema for validating employee filter request data.
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