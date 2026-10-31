"""Serve only the bundled frontend on a loopback listener."""
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, abort, request, send_from_directory


def create_web_app(root):
    root = Path(root).resolve()
    app = Flask('blockhouse_local_web', static_folder=None)

    @app.before_request
    def local_host():
        if urlsplit('http://' + request.host).hostname not in ('127.0.0.1', 'localhost', '::1'):
            abort(403)

    @app.get('/')
    def index():
        return send_from_directory(root, 'index.html')

    @app.get('/assets/<path:name>')
    def asset(name):
        return send_from_directory(root / 'assets', name)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src http://127.0.0.1:5050; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        return response

    return app
