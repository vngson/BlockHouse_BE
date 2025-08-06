from marshmallow import Schema, fields

class EmployeeRevenueSchema(Schema):
    """
    Schema for individual employee revenue data.
    """
    id = fields.Integer()
    name = fields.String()
    revenue = fields.Float()
    order_count = fields.Integer()

class MonthlyRevenueSchema(Schema):
    """
    Schema for monthly revenue data.
    """
    month = fields.Integer()
    revenue = fields.Float()

class DashboardResponseSchema(Schema):
    """
    Schema for dashboard response data.
    """
    top_employees = fields.List(fields.Nested(EmployeeRevenueSchema))
    total_revenue = fields.Float()
    total_service_sales = fields.Integer()
    growth_percent = fields.Float()
    monthly_chart = fields.List(fields.Nested(MonthlyRevenueSchema))