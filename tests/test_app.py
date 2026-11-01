import pytest
from app import create_app, db
from app.models import Observation, RiskAssessment, Alert


@pytest.fixture()
def app():
    app = create_app({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SECRET_KEY': 'test-secret',
        'DEMO_MODE': False,
    })
    with app.app_context():
        db.drop_all()
        db.create_all()
        from app import seed_demo_data
        seed_demo_data(app)
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_public_pages(client):
    for path in ['/', '/dashboard', '/locations', '/satellite', '/risk', '/alerts', '/preparedness', '/data-sources', '/health']:
        response = client.get(path)
        assert response.status_code == 200, path


def test_staff_login_and_role_access(client):
    response = client.post(
        '/login',
        data={'username': 'satellite', 'password': 'Demo123!Change'},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b'Monitoring dashboard' in response.data

    observation_response = client.get('/observations/new')
    assert observation_response.status_code == 200
    assert b'Add observation' in observation_response.data


def test_wrong_role_blocked(client):
    client.post('/login', data={'username': 'satellite', 'password': 'Demo123!Change'})
    assert client.get('/risk/new').status_code == 403


def test_health_json(client):
    data = client.get('/health').get_json()
    assert data['status'] == 'ok'
    assert data['integrations']['weather'] == 'Open-Meteo Forecast API'


def test_fresh_database_has_no_fabricated_hazard_records(app):
    with app.app_context():
        assert Observation.query.count() == 0
        assert RiskAssessment.query.count() == 0
        assert Alert.query.count() == 0


def test_weather_feed_unavailable_state_is_safe(client):
    response = client.get('/dashboard')
    assert response.status_code == 200
    assert b'Current weather' in response.data


def test_satellite_catalogue_page_does_not_require_live_network(client):
    response = client.get('/satellite')
    assert response.status_code == 200
    assert b'Copernicus Sentinel catalogue results' in response.data
    assert b'External feeds are disabled during automated tests' in response.data


def test_repeated_initialization_is_idempotent(app):
    """Calling seed_demo_data twice must not crash or create duplicate users."""
    from app import seed_demo_data
    from app.models import User

    with app.app_context():
        user_count_before = User.query.count()
        # Call seed_demo_data a second time — must not raise or duplicate.
        seed_demo_data(app)
        user_count_after = User.query.count()
        assert user_count_after == user_count_before, (
            f"User count changed from {user_count_before} to {user_count_after} "
            "after repeated seed_demo_data call"
        )
        # The three staff accounts must still exist exactly once each.
        admin = User.query.filter_by(username='admin').all()
        satellite = User.query.filter_by(username='satellite').all()
        risk = User.query.filter_by(username='risk').all()
        assert len(admin) == 1, f"Expected 1 admin, found {len(admin)}"
        assert len(satellite) == 1, f"Expected 1 satellite user, found {len(satellite)}"
        assert len(risk) == 1, f"Expected 1 risk user, found {len(risk)}"
