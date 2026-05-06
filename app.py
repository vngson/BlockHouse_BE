from flask import Flask
from flask_cors import CORS
from models import db
from controllers.sample_routes import sample_bp
from controllers.employee_controller import employee_bp
from controllers.dashboard_controller import dashboard_bp
from controllers.order_controller import order_bp
from controllers.health_controller import health_bp
from controllers.service_controller import service_bp
def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    CORS(app)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(sample_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(service_bp)

    return app

app = create_app()

if __name__ == "__main__":
    app.run()