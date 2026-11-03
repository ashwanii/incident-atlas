import pytest
from fastapi.testclient import TestClient
from app.core import config
from app.main import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'test.sqlite3')
    monkeypatch.setattr(config, 'API_KEY', 'reader-test')
    monkeypatch.setattr(config, 'ADMIN_KEY', 'admin-test')
    with TestClient(app) as c:
        c.headers['X-API-Key'] = 'admin-test'
        yield c

@pytest.fixture
def rca():
    return {'source_key':'wiki/kafka/rca','title':'Kafka lag','kind':'RCA','services':['kafka'],
      'origin':'greenfield','owner':'sre','reviewed_on':'2026-10-01',
      'content':'Root cause: consumer saturation. Impact: events delayed. Timeline: recovered at noon. Corrective actions: expand consumer capacity.'}

@pytest.fixture
def sop():
    return {'source_key':'wiki/kafka/sop','title':'Kafka lag','kind':'SOP','services':['kafka'],
      'origin':'greenfield','owner':'sre','reviewed_on':'2026-10-01',
      'content':'Prerequisites: obtain approval.\nSteps\n1. Record lag.\n2. Check consumer capacity.\n3. Scale within approved limits.\nVerification: lag decreases.\nRollback: restore previous count.'}
