from marshmallow import Schema, fields

class OrderServiceResponseSchema(Schema):
    """
    Schema for serializing order service response data.
    """
    service_id = fields.Integer()
    quantity = fields.Integer()
    name = fields.String(dump_only=True)

class OrderResponseSchema(Schema):
    """
    Schema for serializing order response data.
    """
    id = fields.Integer(dump_only=True)
    datetime = fields.DateTime()
    employee_id = fields.Integer(allow_none=True)
    employee_name = fields.String(dump_only=True)
    promotion_id = fields.Integer(allow_none=True)
    total = fields.Float(allow_none=True, as_string=True)
    services = fields.List(fields.Nested(OrderServiceResponseSchema), dump_only=True)