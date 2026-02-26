#!/bin/bash
set -e

# Create base tables (user, job, client, worker, etc.) if they don't exist
# This must run BEFORE alembic so migrations can reference these tables
python -c "
from app.database import create_db_and_tables
create_db_and_tables()
print('Base tables created/verified')
"

# If alembic_version table doesn't exist but the database has tables,
# stamp at head so alembic doesn't re-run migrations on existing tables
python -c "
from app.database import engine
from sqlalchemy import inspect
with engine.connect() as conn:
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    has_alembic = 'alembic_version' in tables
    if not has_alembic and 'job' in tables:
        import subprocess
        subprocess.run(['alembic', 'stamp', 'head'], check=True)
        print('Stamped alembic at head (fresh database with tables)')
    elif has_alembic:
        print('Alembic version table exists, will upgrade normally')
    else:
        print('No tables found, unexpected state')
"

# Run pending migrations
alembic upgrade head

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
