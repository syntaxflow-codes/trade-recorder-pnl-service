from alembic import context
from sqlalchemy import create_engine, pool
from app.database import Base, database_url
from app import models

target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=database_url().render_as_string(hide_password=False), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = create_engine(database_url(), poolclass=pool.NullPool, connect_args={"options": "-c timezone=UTC"})
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
