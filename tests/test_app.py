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
