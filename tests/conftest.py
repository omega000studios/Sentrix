import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url

from app.db import Base, make_engine


def validate_test_database(url, working_url):
    target = make_url(url)
    if not target.drivername.startswith('postgres') or not (target.database or '').endswith('_test'):
        raise ValueError('TEST_DATABASE_URL must name a disposable Postgres database ending in _test')
    if working_url:
        working = make_url(working_url)
        if (working.host, working.port or 5432, working.database) == (target.host, target.port or 5432, target.database):
            raise ValueError('The test database must differ from DATABASE_URL')


@pytest.fixture(params=["sqlite", "postgres"])
def factory(request, tmp_path, monkeypatch):
    if request.param == "postgres":
        url = os.getenv("TEST_DATABASE_URL")
        if not url:
            pytest.skip("Set TEST_DATABASE_URL to a disposable Postgres database")
        validate_test_database(url, os.getenv('DATABASE_URL'))
        # Explicit opt-in: migrations and cleanup target only the test database.
        monkeypatch.setenv("DATABASE_URL", url)
        command.upgrade(Config("alembic.ini"), "head")
        engine = make_engine(url)
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        with engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(table.delete())
        engine.dispose()
