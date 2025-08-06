from flask import Flask
from models import db
from controllers.sample_routes import sample_bp
from controllers.employee_controller import employee_bp
from controllers.dashboard_controller import dashboard_bp
from controllers.order_controller import order_bp
def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(sample_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(order_bp)

    return app

app = create_app()

if __name__ == "__main__":
    app.run()