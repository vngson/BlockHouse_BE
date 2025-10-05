from marshmallow import Schema, fields

class EmployeeRevenueSchema(Schema):
    """
    Schema for individual employee revenue data.
    """
    id = fields.Integer()
    name = fields.String()
    revenue = fields.Float()
    order_count = fields.Integer()

class MonthlyServiceDataSchema(Schema):
    """
    Schema for monthly service data (quantity and revenue per month).
    """
    month = fields.Integer()
    quantity = fields.Integer()
    revenue = fields.Float()

class ServiceChartSchema(Schema):
    """
    Schema for service chart data, including monthly data.
    """
    service_id = fields.Integer()
    service_name = fields.String()
    monthly_data = fields.List(fields.Nested(MonthlyServiceDataSchema))

class DashboardResponseSchema(Schema):
    """
    Schema for dashboard response data.
    """
    top_employees = fields.List(fields.Nested(EmployeeRevenueSchema))
    total_revenue = fields.Float()
    total_service_sales = fields.Integer()
    growth_percent = fields.Float()
    monthly_chart = fields.List(fields.Nested(ServiceChartSchema))