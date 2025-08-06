from marshmallow import Schema, fields

class EmployeeResponseSchema(Schema):
    """
    Schema for serializing employee response data.
    """
    id = fields.Integer(dump_only=True)
    name = fields.String()
    phone = fields.String(allow_none=True)
    status = fields.Integer()
    income = fields.Decimal(allow_none=True, as_string=True)