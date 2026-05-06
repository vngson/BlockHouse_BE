from marshmallow import Schema, fields

class OrderServiceResponseSchema(Schema):
    """
    Schema for serializing OrderServiceModel data.
    """
    service_id = fields.Integer()
    name = fields.String()
    quantity = fields.Integer()

class OrderResponseSchema(Schema):
    """
    Schema for serializing Order data.
    """
    id = fields.Integer()
    datetime = fields.DateTime()
    employee_id = fields.Integer(allow_none=True)
    employee_name = fields.String(allow_none=True)
    promotion_id = fields.Integer(allow_none=True)
    total = fields.Float()
    services = fields.List(fields.Nested(OrderServiceResponseSchema))
    created_at = fields.DateTime()
    updated_at = fields.DateTime()

class OrdersByDateResponseSchema(Schema):
    """
    Schema for serializing orders grouped by date.
    """
    date = fields.Date()
    total = fields.Float()
    services = fields.List(fields.Nested(OrderServiceResponseSchema))
    employee_id = fields.Integer(allow_none=True)
    promotion_id = fields.Integer(allow_none=True)

class OrdersForOneDateResponseSchema(Schema):
    """
    Schema for serializing orders for a specific date.
    """
    date = fields.Date()
    total = fields.Float()
    services = fields.List(fields.Nested(OrderServiceResponseSchema))
    employee_id = fields.Integer(allow_none=True)
    promotion_id = fields.Integer(allow_none=True)

class RevenueByEmployeeResponseSchema(Schema):
    """
    Schema for serializing revenue data grouped by date and employee.
    """
    date = fields.Date()
    employee_id = fields.Integer()
    employee_name = fields.String()
    total = fields.Float()
    services = fields.List(fields.Nested(OrderServiceResponseSchema))

class RevenueByEmployeeMonthlyResponseSchema(Schema):
    """
    Schema for serializing monthly revenue data by employee.
    """
    year = fields.Integer()
    month = fields.Integer()
    employee_id = fields.Integer()
    employee_name = fields.String()
    total = fields.Float()
    order_count = fields.Integer()  # Số đơn hàng trong tháng
    services = fields.List(fields.Nested(OrderServiceResponseSchema))