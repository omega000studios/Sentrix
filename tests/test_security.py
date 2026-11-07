import pytest
from sqlalchemy import event, func, select

from app.db import Label, Verdict
from conftest import validate_test_database
from test_api import client, load


@pytest.mark.parametrize('url,working', [
    ('postgresql://user:password@localhost/demo', None),
    ('sqlite:///demo_test', None),
    ('postgresql://user:password@localhost/demo_test', 'postgresql+psycopg://other:password@localhost:5432/demo_test'),
])
def test_reject_unsafe_test_database(url, working):
    with pytest.raises(ValueError):
        validate_test_database(url, working)


def test_accept_separate_disposable_test_database():
    validate_test_database('postgresql://user:password@localhost/demo_test', 'postgresql://user:password@localhost/demo')


def test_sensitive_responses_are_not_cached_or_framed(factory):
    load(factory)
    with client(factory) as api:
        for path in ('/', '/orders', '/static/dashboard.js'):
            response = api.get(path)
            assert response.status_code == 200
            assert response.headers['cache-control'] == 'no-store'
            assert response.headers['x-frame-options'] == 'DENY'
            assert response.headers['x-content-type-options'] == 'nosniff'
            assert response.headers['referrer-policy'] == 'no-referrer'
        assert "script-src 'self'" in api.get('/').headers['content-security-policy']
        assert api.get('/orders', auth=('merchant', 'wrong')).headers['cache-control'] == 'no-store'


def test_commit_failure_does_not_report_success(factory):
    _, _, label = load(factory)

    def fail_commit(session):
        raise RuntimeError('simulated commit failure')

    event.listen(factory, 'before_commit', fail_commit)
    try:
        with client(factory) as api:
            response = api.post('/labels', json=label)
            assert response.status_code == 500
            assert response.json() == {'detail': 'Internal server error'}
            assert response.headers['cache-control'] == 'no-store'
    finally:
        event.remove(factory, 'before_commit', fail_commit)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Label)) == 0
        assert db.scalar(select(func.count()).select_from(Verdict)) == 0
