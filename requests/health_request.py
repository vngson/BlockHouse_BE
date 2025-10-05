from marshmallow import Schema

class HealthRequestSchema(Schema):
    """
    Schema for validating health check request parameters.
    No parameters are required for health check.
    """
    pass