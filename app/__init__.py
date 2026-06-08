from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')

    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    from app.auth import auth_bp
    from app.gigs import gigs_bp
    from app.orders import orders_bp
    from app.chat import chat_bp
    from app.admin import admin_bp
    
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(gigs_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(chat_bp)

    with app.app_context():
        from app import models
        db.create_all()

    from app.scheduler import start_scheduler
    start_scheduler(app)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    return app