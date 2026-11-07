import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine


@pytest.fixture(params=["sqlite", "postgres"])
def factory(request, tmp_path, monkeypatch):
    if request.param == "postgres":
        url = os.getenv("TEST_DATABASE_URL")
        if not url:
            pytest.skip("Set TEST_DATABASE_URL to a disposable Postgres database")
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
