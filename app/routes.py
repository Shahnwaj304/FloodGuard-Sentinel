from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_user, logout_user, login_required, current_user
from . import db
from .models import User, Location, Observation, RiskAssessment, Alert, PreparednessResource
from .services.live_data import get_current_weather, get_satellite_catalogue

main = Blueprint('main', __name__)
ROLES = ['Administrator', 'Satellite Data Officer', 'Risk & Alert Officer', 'Public User']


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator

@main.app_context_processor
def inject_globals():
    return {'app_name': 'FloodGuard Sentinel', 'demo_mode': current_app.config.get('DEMO_MODE', True)}

@main.route('/')
def index():
    locations = Location.query.filter_by(active=True).all()
    alerts_query = Alert.query.order_by(Alert.created_at.desc())
    observations_query = Observation.query.order_by(Observation.observed_at.desc())
    if not current_app.config.get('DEMO_MODE', False):
        alerts_query = alerts_query.filter_by(is_demo=False)
        observations_query = observations_query.filter_by(is_demo=False)
    alerts = alerts_query.limit(5).all()
    observations = observations_query.limit(5).all()
    return render_template('index.html', locations=locations, alerts=alerts, observations=observations)

@main.route('/dashboard')
def dashboard():
    locations = Location.query.filter_by(active=True).all()
    assessments_query = RiskAssessment.query.order_by(RiskAssessment.created_at.desc())
    alerts_query = Alert.query.order_by(Alert.created_at.desc())
    observations_query = Observation.query.order_by(Observation.observed_at.desc())
    if not current_app.config.get('DEMO_MODE', False):
        assessments_query = assessments_query.filter_by(is_demo=False)
        alerts_query = alerts_query.filter_by(is_demo=False)
        observations_query = observations_query.filter_by(is_demo=False)
    assessments = assessments_query.limit(6).all()
    alerts = alerts_query.limit(6).all()
    observations = observations_query.limit(6).all()
    weather = get_current_weather(locations, testing=current_app.testing)
    map_points = [{'name': l.name, 'district': l.district, 'lat': l.latitude, 'lon': l.longitude, 'hazard': l.hazard_type} for l in locations]
    return render_template('dashboard.html', locations=locations, assessments=assessments, alerts=alerts, observations=observations, map_points=map_points, weather=weather)

@main.route('/locations')
def locations():
    q = request.args.get('q', '').strip()
    query = Location.query.filter_by(active=True)
    if q:
        query = query.filter(db.or_(Location.name.ilike(f'%{q}%'), Location.district.ilike(f'%{q}%'), Location.hazard_type.ilike(f'%{q}%')))
    return render_template('locations.html', locations=query.order_by(Location.name).all(), q=q)

@main.route('/locations/<int:location_id>')
def location_detail(location_id):
    location = db.get_or_404(Location, location_id)
    observations = Observation.query.filter_by(location_id=location.id).order_by(Observation.observed_at.desc()).all()
    assessments = RiskAssessment.query.filter_by(location_id=location.id).order_by(RiskAssessment.created_at.desc()).all()
    alerts = Alert.query.filter_by(location_id=location.id).order_by(Alert.created_at.desc()).all()
    return render_template('location_detail.html', location=location, observations=observations, assessments=assessments, alerts=alerts)

@main.route('/satellite')
def satellite():
    query = Observation.query.order_by(Observation.observed_at.desc())
    if not current_app.config.get('DEMO_MODE', False):
        query = query.filter_by(is_demo=False)
    observations = query.all()
    catalogue = get_satellite_catalogue(testing=current_app.testing)
    return render_template('satellite.html', observations=observations, catalogue=catalogue)

@main.route('/observations/new', methods=['GET', 'POST'])
@roles_required('Satellite Data Officer', 'Administrator')
def observation_new():
    if request.method == 'POST':
        location_id = request.form.get('location_id', type=int)
        location = db.session.get(Location, location_id)
        source = request.form.get('source', '').strip()
        kind = request.form.get('observation_type', '').strip()
        summary = request.form.get('summary', '').strip()
        if not location or not source or not kind or not summary:
            flash('Please complete all required fields.', 'danger')
        else:
            observed_at = datetime.now(timezone.utc)
            item = Observation(location_id=location.id, source=source, observation_type=kind, summary=summary, observed_at=observed_at, status='Pending review', is_demo=current_app.config.get('DEMO_MODE', True))
            db.session.add(item); db.session.commit()
            flash('Observation saved. It is pending review and is labelled as demo data when demo mode is enabled.', 'success')
            return redirect(url_for('main.satellite'))
    return render_template('observation_form.html', locations=Location.query.filter_by(active=True).all())

@main.route('/risk')
def risk():
    query = RiskAssessment.query.order_by(RiskAssessment.created_at.desc())
    if not current_app.config.get('DEMO_MODE', False):
        query = query.filter_by(is_demo=False)
    assessments = query.all()
    return render_template('risk.html', assessments=assessments)

@main.route('/risk/new', methods=['GET', 'POST'])
@roles_required('Risk & Alert Officer', 'Administrator')
def risk_new():
    levels = ['Normal', 'Watch', 'High concern', 'Critical', 'Unknown / insufficient data']
    if request.method == 'POST':
        location = db.session.get(Location, request.form.get('location_id', type=int))
        level = request.form.get('level', '')
        rationale = request.form.get('rationale', '').strip()
        if not location or level not in levels or len(rationale) < 15:
            flash('Choose a location and valid level, and provide a rationale of at least 15 characters.', 'danger')
        else:
            db.session.add(RiskAssessment(location_id=location.id, level=level, rationale=rationale, created_by=current_user.username, is_demo=current_app.config.get('DEMO_MODE', True)))
            db.session.commit(); flash('Assessment recorded. This is not a scientific forecast or official warning.', 'success')
            return redirect(url_for('main.risk'))
    return render_template('risk_form.html', locations=Location.query.filter_by(active=True).all(), levels=levels)

@main.route('/alerts')
def alerts():
    query = Alert.query.order_by(Alert.created_at.desc())
    if not current_app.config.get('DEMO_MODE', False):
        query = query.filter_by(is_demo=False)
    return render_template('alerts.html', alerts=query.all())

@main.route('/alerts/new', methods=['GET', 'POST'])
@roles_required('Risk & Alert Officer', 'Administrator')
def alert_new():
    if request.method == 'POST':
        location = db.session.get(Location, request.form.get('location_id', type=int))
        title = request.form.get('title', '').strip()
        severity = request.form.get('severity', '')
        message = request.form.get('message', '').strip()
        if not location or not title or severity not in ['Watch', 'High concern', 'Critical', 'Informational'] or len(message) < 15:
            flash('Complete all fields with a valid severity and a meaningful message.', 'danger')
        else:
            # All new alerts remain Draft; no real public notifications are sent by this MVP.
            db.session.add(Alert(location_id=location.id, title=title, severity=severity, status='Draft', message=message, is_demo=current_app.config.get('DEMO_MODE', True)))
            db.session.commit(); flash('Alert saved as Draft. No emergency notification was sent.', 'success')
            return redirect(url_for('main.alerts'))
    return render_template('alert_form.html', locations=Location.query.filter_by(active=True).all())

@main.route('/preparedness')
def preparedness():
    resources = PreparednessResource.query.order_by(PreparednessResource.category, PreparednessResource.title).all()
    return render_template('preparedness.html', resources=resources)

@main.route('/data-sources')
def data_sources():
    return render_template('data_sources.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username, active=True).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome, {user.display_name}.', 'success')
            return redirect(request.args.get('next') or url_for('main.dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@main.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user(); flash('You have been signed out.', 'info')
    return redirect(url_for('main.index'))

@main.route('/control-room')
@roles_required('Administrator', 'Risk & Alert Officer')
def control_room():
    return render_template('control_room.html', location_count=Location.query.count(), observation_count=Observation.query.count(), assessment_count=RiskAssessment.query.count(), alert_count=Alert.query.count(), users_count=User.query.count())

@main.route('/admin/users')
@roles_required('Administrator')
def admin_users():
    return render_template('admin_users.html', users=User.query.order_by(User.username).all())

@main.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@roles_required('Administrator')
def toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'warning')
    else:
        user.active = not user.active; db.session.commit(); flash('User status updated.', 'success')
    return redirect(url_for('main.admin_users'))

@main.route('/health')
def health():
    return {
        'status': 'ok',
        'application': 'FloodGuard Sentinel',
        'demo_mode': current_app.config.get('DEMO_MODE', False),
        'integrations': {
            'weather': 'Open-Meteo Forecast API',
            'satellite_catalogue': 'Copernicus Data Space STAC API',
            'official_warnings': 'External official source links; not automatically issued by this app',
        },
    }, 200

@main.app_errorhandler(403)
def forbidden(_error):
    return render_template('error.html', code=403, message='You do not have permission to access this page.'), 403

@main.app_errorhandler(404)
def not_found(_error):
    return render_template('error.html', code=404, message='The page or record you requested was not found.'), 404
