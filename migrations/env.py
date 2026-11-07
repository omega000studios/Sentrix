import os

from alembic import context

from app.db import Base, make_engine


with make_engine(os.environ["DATABASE_URL"]).connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
