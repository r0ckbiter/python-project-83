import pytest
from page_analyzer.app import app


@pytest.fixture()
def get_app():
    app.config.update({"TESTING": True})
    yield app


@pytest.fixture()
def client(get_app):
    return get_app.test_client()


def test_home_page(client):
    response = client.get('/')
    assert response.status_code == 200
    assert "<title>Анализатор страниц</title>" in response.text
