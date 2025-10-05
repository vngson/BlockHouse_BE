from marshmallow import Schema, fields

class ServiceResponseSchema(Schema):
    """
    Schema for single service response data.
    """
    id = fields.Integer()
    name = fields.String()
    description = fields.String(allow_none=True)
    price = fields.Float()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()

class ServiceListResponseSchema(Schema):
    """
    Schema for list of services response data with pagination.
    """
    services = fields.List(fields.Nested(ServiceResponseSchema))
    page = fields.Integer(dump_only=True)
    page_size = fields.Integer(dump_only=True)
    total_services = fields.Integer(dump_only=True)