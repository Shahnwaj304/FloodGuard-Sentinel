import os
from datetime import datetime, timedelta, timezone
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app_env = os.getenv('APP_ENV', 'development').lower()
    configured_secret = os.getenv('SECRET_KEY', '').strip()
    initial_staff_password = os.getenv('INITIAL_STAFF_PASSWORD', '').strip()
    if app_env == 'production' and (not configured_secret or configured_secret == 'dev-only-change-me' or configured_secret.startswith('replace-')):
        raise RuntimeError('Set a strong SECRET_KEY before running FloodGuard Sentinel in production.')
    if app_env == 'production' and (not initial_staff_password or initial_staff_password == 'Demo123!Change' or initial_staff_password.startswith('replace-')):
        raise RuntimeError('Set a unique INITIAL_STAFF_PASSWORD before running in production.')
    app.config.from_mapping(
        SECRET_KEY=configured_secret or 'dev-only-change-me',
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///floodguard.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        DEMO_MODE=os.getenv('DEMO_MODE', 'false').lower() == 'true',
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=app_env == 'production',
        SESSION_COOKIE_SAMESITE='Lax',
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message_category = 'info'
    csrf.init_app(app)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
        return response

    from .models import User, Location, Observation, RiskAssessment, Alert, PreparednessResource
    from .routes import main
    app.register_blueprint(main)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    with app.app_context():
        db.create_all()
        if not User.query.first():
            seed_demo_data(app)
        # Remove legacy illustrative records when operating in real-data mode.
        # Keep staff-created non-demo records and configured monitoring locations.
        if not app.config.get('DEMO_MODE', False):
            for model in (Observation, RiskAssessment, Alert):
                model.query.filter_by(is_demo=True).delete(synchronize_session=False)
            db.session.commit()
    configure_cloudwatch_logging(app)
    return app


def configure_cloudwatch_logging(app):
    """Optionally ship application logs to CloudWatch when configured in AWS."""
    log_group = os.getenv('CLOUDWATCH_LOG_GROUP', '').strip()
    if not log_group:
        return
    try:
        import boto3
        from watchtower import CloudWatchLogHandler
        handler = CloudWatchLogHandler(
            boto3_client=boto3.client('logs', region_name=os.getenv('AWS_REGION', 'ap-south-1')),
            log_group_name=log_group,
            stream_name=os.getenv('CLOUDWATCH_LOG_STREAM', 'floodguard-app'),
            create_log_group=False,
        )
        handler.setLevel(os.getenv('LOG_LEVEL', 'INFO').upper())
        app.logger.addHandler(handler)
        app.logger.setLevel(os.getenv('LOG_LEVEL', 'INFO').upper())
        app.logger.info('CloudWatch logging configured for FloodGuard Sentinel')
    except Exception as exc:
        # Logging integration must never prevent the local app from starting.
        app.logger.warning('CloudWatch logging could not be configured: %s', exc)


def seed_demo_data(app):
    """Create initial staff accounts, configured locations and preparedness guidance.

    No fabricated observations, risk assessments or alerts are seeded. Current
    weather and satellite catalogue metadata are retrieved by live-data adapters.
    """
    from .models import User, Location, PreparednessResource

    users = [
        User(username='admin', email='admin@floodguard.local', role='Administrator', display_name='System Administrator'),
        User(username='satellite', email='satellite@floodguard.local', role='Satellite Data Officer', display_name='Satellite Data Officer'),
        User(username='risk', email='risk@floodguard.local', role='Risk & Alert Officer', display_name='Risk & Alert Officer'),
    ]
    for user in users:
        user.set_password(os.getenv('INITIAL_STAFF_PASSWORD', '').strip() or 'Demo123!Change')
        db.session.add(user)

    # Configured monitoring sites, not reports of current hazard events.
    locations = [
        Location(name='Imja Tsho', district='Solukhumbu', hazard_type='Glacial lake / GLOF', latitude=27.898, longitude=86.929, description='Configured monitoring location in the Everest region. Coordinates should be verified against an authoritative gazetteer before operational use.'),
        Location(name='Melamchi River', district='Sindhupalchok', hazard_type='Flash flood / debris flow', latitude=27.835, longitude=85.570, description='Configured river monitoring corridor. No live flood status is implied.'),
        Location(name='Koshi River Corridor', district='Sunsari', hazard_type='River flooding', latitude=26.665, longitude=87.160, description='Configured downstream monitoring corridor. No live flood status is implied.'),
        Location(name='Seti River', district='Kaski', hazard_type='Flash flood', latitude=28.250, longitude=83.950, description='Configured monitoring location for rapid-onset flood awareness. No live hazard status is implied.'),
    ]
    db.session.add_all(locations)
    resources = [
        PreparednessResource(title='Prepare an emergency kit', category='Preparedness', body='Keep drinking water, essential medicines, a torch, batteries, copies of important documents and a charged phone ready.'),
        PreparednessResource(title='Know your evacuation route', category='Planning', body='Identify safe higher ground and local evacuation routes in advance. Follow instructions from authorised local officials.'),
        PreparednessResource(title='Use official warnings', category='Reliable information', body='Check Nepal Department of Hydrology and Meteorology and local authorities for verified forecasts and emergency instructions.'),
    ]
    db.session.add_all(resources)
    db.session.commit()
