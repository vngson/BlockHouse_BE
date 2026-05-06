from datetime import datetime, date
import random
from app import create_app
from models import db
from models.employee_model import Employee, EmployeeStatus
from models.service_model import Service
from models.promotion_model import Promotion
from models.order_model import Order
from models.order_service_model import OrderServiceModel

def create_mock_data():
    app = create_app()

    with app.app_context():
        db.drop_all()
        db.create_all()

        print("Creating employees...")
        employees = [
            Employee(name="Nguyễn Văn An", phone="0901234567", status=EmployeeStatus.ACTIVE, income=0),
            Employee(name="Trần Thị Bình", phone="0912345678", status=EmployeeStatus.ACTIVE, income=0),
            Employee(name="Lê Văn Cường", phone="0923456789", status=EmployeeStatus.ACTIVE, income=0),
            Employee(name="Phạm Thị Dung", phone="0934567890", status=EmployeeStatus.ACTIVE, income=0),
            Employee(name="Hoàng Văn Em", phone="0945678901", status=EmployeeStatus.INACTIVE, income=0),
        ]
        for emp in employees:
            db.session.add(emp)
        db.session.commit()
        print(f"Created {len(employees)} employees")

        print("\nCreating services...")
        services = [
            Service(name="Cắt tóc nam", description="Cắt tóc nam cơ bản", price=50000),
            Service(name="Cắt tóc nữ", description="Cắt tóc nữ cơ bản", price=80000),
            Service(name="Nhuộm tóc", description="Nhuộm tóc nhiều màu", price=300000),
            Service(name="Uốn tóc", description="Uốn tóc đẹp", price=250000),
            Service(name="Gội đầu", description="Gội đầu thư giãn", price=60000),
            Service(name="Chăm sóc da mặt", description="Chăm sóc da mặt chuyên sâu", price=200000),
            Service(name="Tẩy lông", description="Tẩy lông toàn thân", price=150000),
            Service(name="Massage chân", description="Massage chân thư giãn", price=100000),
        ]
        for svc in services:
            db.session.add(svc)
        db.session.commit()
        print(f"Created {len(services)} services")

        print("\nCreating promotions for May 2026...")
        promotions = [
            Promotion(
                name="Khuyến mãi 1/5",
                description="Giảm giá 20% cho tất cả dịch vụ",
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 5),
                value=20,
                type="PERCENT"
            ),
            Promotion(
                name="Happy Hour",
                description="Giảm giá 10% cho dịch vụ gội đầu",
                start_date=date(2026, 5, 10),
                end_date=date(2026, 5, 15),
                value=10,
                type="PERCENT"
            ),
            Promotion(
                name="Đặc biệt tháng 5",
                description="Giảm 50k cho hóa đơn trên 300k",
                start_date=date(2026, 5, 16),
                end_date=date(2026, 5, 31),
                value=50000,
                type="AMOUNT"
            ),
        ]
        for promo in promotions:
            db.session.add(promo)
        db.session.commit()
        print(f"Created {len(promotions)} promotions")

        print("\nCreating orders for May 2026...")
        orders = []
        may_2026_start = datetime(2026, 5, 1, 8, 0)
        may_2026_end = datetime(2026, 5, 31, 21, 0)

        num_orders = 200
        for i in range(num_orders):
            random_date = datetime.fromtimestamp(
                random.uniform(may_2026_start.timestamp(), may_2026_end.timestamp())
            )

            active_employees = [e for e in employees if e.status == EmployeeStatus.ACTIVE]
            emp = random.choice(active_employees)

            total = random.uniform(50000, 500000)
            promo = random.choice(promotions + [None])

            order = Order(
                datetime=random_date,
                employee_id=emp.id,
                promotion_id=promo.id if promo else None,
                total=total
            )
            orders.append(order)
            db.session.add(order)
        db.session.commit()
        print(f"Created {len(orders)} orders")

        print("\nCreating order-service relationships...")
        for order in orders:
            num_services = random.randint(1, 3)
            selected_services = random.sample(services, num_services)

            for svc in selected_services:
                quantity = random.randint(1, 2)
                order_service = OrderServiceModel(
                    order_id=order.id,
                    service_id=svc.id,
                    quantity=quantity
                )
                db.session.add(order_service)
        db.session.commit()
        print(f"Created order-service relationships")

        print("\nUpdating employee income based on orders...")
        employee_incomes = {emp.id: 0 for emp in employees}

        for order in orders:
            if order.employee_id in employee_incomes:
                employee_incomes[order.employee_id] += order.total

        for emp in employees:
            emp.income = employee_incomes.get(emp.id, 0)
        db.session.commit()

        print("\n=== Mock Data Summary ===")
        print(f"Employees: {Employee.query.count()}")
        print(f"Services: {Service.query.count()}")
        print(f"Promotions: {Promotion.query.count()}")
        print(f"Orders: {Order.query.count()}")
        print(f"Order-Services: {OrderServiceModel.query.count()}")

        print("\n=== Employee Income for May 2026 ===")
        for emp in employees:
            print(f"{emp.name}: {emp.income:,.0f} VND")

        print("\n=== Daily Order Statistics (May 2026) ===")
        from sqlalchemy import func
        daily_stats = db.session.query(
            func.date(Order.datetime).label('date'),
            func.count(Order.id).label('count'),
            func.sum(Order.total).label('total')
        ).group_by(func.date(Order.datetime)).order_by(func.date(Order.datetime)).all()

        for day, count, total in daily_stats:
            print(f"{day}: {count} orders, Total: {total:,.0f} VND")

if __name__ == "__main__":
    create_mock_data()
    print("\nMock data created successfully!")
