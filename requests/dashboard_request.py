from marshmallow import Schema, fields, validates, ValidationError

class DashboardRequestSchema(Schema):
    """
    Schema for validating dashboard request parameters.
    """
    month = fields.Integer(required=False, allow_none=True, validate=lambda x: 1 <= x <= 12 if x is not None else True)
    year = fields.Integer(required=False, allow_none=True, validate=lambda x: x >= 2000 if x is not None else True)

    @validates('month')
    def validate_month(self, value, **kwargs):
        """Validate month is between 1 and 12"""
        if value is not None and not (1 <= value <= 12):
            raise ValidationError('Month must be between 1 and 12')

    @validates('year')
    def validate_year(self, value, **kwargs):
        """Validate year is reasonable"""
        if value is not None and value < 2000:
            raise ValidationError('Year must be 2000 or later')