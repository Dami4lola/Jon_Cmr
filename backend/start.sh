#!/bin/bash
set -e

# If alembic_version table doesn't exist but the database has tables,
# stamp it at 0001 so only migration 0002+ runs
python -c "
from app.database import engine
from sqlalchemy import inspect
with engine.connect() as conn:
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    has_alembic = 'alembic_version' in tables
    if not has_alembic and 'job' in tables:
        cols = [c['name'] for c in inspector.get_columns('job')]
        if 'scheduled_date' in cols:
            import subprocess
            subprocess.run(['alembic', 'stamp', '0001'], check=True)
            print('Stamped alembic at 0001 (existing database)')
        else:
            print('Database already has new schema, skipping stamp')
    elif has_alembic:
        print('Alembic version table exists, will upgrade normally')
    else:
        print('Fresh database, will run all migrations')
"

# Run pending migrations
alembic upgrade head

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
