from marshmallow import Schema, fields, validates, ValidationError
import re

class EmployeeRequestSchema(Schema):
    """
    Schema for validating employee request data.
    """
    name = fields.String(required=True, validate=lambda x: len(x.strip()) > 0)
    phone = fields.String(allow_none=True)
    status = fields.Integer(allow_none=True)
    income = fields.Decimal(allow_none=True)

    @validates('phone')
    def validate_phone(self, value, **kwargs):
        """Validate phone number format"""
        if value and not re.match(r'^\+?1?\d{9,15}$', value):
            raise ValidationError('Invalid phone number format')

    @validates('status')
    def validate_status(self, value, **kwargs):
        """Validate status is either 0 or 1"""
        if value is not None and value not in [0, 1]:
            raise ValidationError('Status must be 0 (inactive) or 1 (active)')
        
class EmployeeFilterRequestSchema(Schema):
    """
    Schema for validating employee filter request data.
    """
    start_date = fields.Date(allow_none=True)
    end_date = fields.Date(allow_none=True)
    page = fields.Integer(load_default=1, validate=lambda x: x >= 1)

    @validates('end_date')
    def validate_end_date(self, value, **kwargs):
        """Ensure end_date is not before start_date"""
        if 'start_date' in self.context and self.context['start_date'] and value:
            if value < self.context['start_date']:
                raise ValidationError('end_date must not be before start_date')