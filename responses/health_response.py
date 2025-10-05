from marshmallow import Schema, fields

class HealthResponseSchema(Schema):
    """
    Schema for health check response data.
    """
    status = fields.String()
    timestamp = fields.String()