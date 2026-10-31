from flask import Flask
from config import Config
from models import db
from controllers.sample_routes import sample_bp
from controllers.employee_controller import employee_bp
from controllers.dashboard_controller import dashboard_bp
from controllers.order_controller import order_bp
from controllers.health_controller import health_bp
from controllers.service_controller import service_bp


def create_app(config_override=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_override:
        app.config.update(config_override)
    app.url_map.strict_slashes = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        from web_api import register_web_api
        register_web_api(app, db.engine.url.database)
    for blueprint in (sample_bp, employee_bp, dashboard_bp, order_bp, health_bp, service_bp):
        app.register_blueprint(blueprint)
    return app


def main():
    import argparse
    import sys
    from pathlib import Path
    parser = argparse.ArgumentParser(description='BlockHouse local backend')
    parser.add_argument('--port', type=int, default=5050)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--web-port', type=int, default=8080, help='Loopback frontend port; 0 disables local web')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--data-dir', help='Absolute data folder for installed BlockHouse')
    parser.add_argument('--import-db', help='Import an existing SQLite DB without overwriting data, then exit')
    args = parser.parse_args()
    from runtime import prepare_runtime, import_database
    data_dir, installed_db, instance_lock = prepare_runtime(args.data_dir)
    if args.import_db:
        if not installed_db:
            parser.error('--import-db requires --data-dir')
        import_database(args.import_db, installed_db)
        sys.exit(0)
    override = {'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(installed_db), 'WEB_SETTINGS_PATH': str(data_dir / 'backend-config.json')} if installed_db else None
    if args.demo:
        if args.host != '127.0.0.1':
            parser.error('Demo only listens on 127.0.0.1.')
        demo_root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
        demo_path = demo_root / 'demo-web.sqlite3'
        override = {'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(demo_path), 'WEB_DEMO': True}
    # Reserve the port before Waitress starts; Windows must not share it with another BE.
    import socket
    api_socket = socket.socket(socket.AF_INET6 if ':' in args.host else socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform == 'win32':
        api_socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        api_socket.bind((args.host, args.port))
    except OSError as error:
        api_socket.close()
        raise RuntimeError(f'Cannot start BlockHouse API on {args.host}:{args.port}. Check whether another BE is already running.') from error
    app = create_app(override)
    if args.demo:
        from web_demo import seed_demo
        seed_demo(app.config['WEB_DATABASE'])
    from waitress import create_server
    if sys.stdout:
        print(f'BlockHouse API: http://{args.host}:{args.port}/api/web', flush=True)
    if not args.demo:
        app.extensions['blockhouse_backups'].start(app.config['WEB_BACKUP_HOURS'])
    server = create_server(app, sockets=[api_socket])
    servers = [server]
    web_root = (Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent) / 'web'
    if args.web_port and (web_root / 'index.html').is_file():
        import logging
        import socket
        from local_web import create_web_app
        web_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Bind before adding the web listener to the API event loop.
            web_socket.bind(('127.0.0.1', args.web_port))
            web_server = create_server(create_web_app(web_root), map=server._map, sockets=[web_socket])
            servers.append(web_server)
            app.config['ALLOWED_ORIGINS'].update({f'http://127.0.0.1:{args.web_port}', f'http://localhost:{args.web_port}'})
            logging.info('BlockHouse local web: http://127.0.0.1:%s', args.web_port)
            if sys.stdout:
                print(f'BlockHouse Web: http://127.0.0.1:{args.web_port}', flush=True)
        except OSError:
            web_socket.close()
            logging.exception('Local web port %s is unavailable; API and Desktop remain available', args.web_port)
    from runtime import install_stop_handler
    install_stop_handler(*servers)
    server.run()


if __name__ == '__main__':
    import logging
    import sys
    try:
        main()
    except Exception as error:
        logging.exception('BlockHouse backend startup failed')
        if sys.stderr:
            print(f'BlockHouse startup failed: {error}', file=sys.stderr, flush=True)
        sys.exit(1)
