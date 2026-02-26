#!/bin/bash
set -e

# Create base tables, check state, and stamp alembic — all in one process
python -c "
import subprocess
from app.database import create_db_and_tables, engine
from app.config import settings
from sqlalchemy import inspect

print(f'DATABASE_URL starts with: {str(engine.url)[:30]}...')

# Create all base tables (user, job, client, worker, timesheet, etc.)
create_db_and_tables()

# Verify and handle alembic
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f'Tables after create_all: {sorted(tables)}')

has_alembic = 'alembic_version' in tables
has_job = 'job' in tables

if has_job and not has_alembic:
    subprocess.run(['alembic', 'stamp', 'head'], check=True)
    print('Stamped alembic at head (fresh database)')
elif has_alembic:
    print('Alembic exists, will upgrade normally')
elif not has_job:
    print('ERROR: create_all did not create tables!')
    exit(1)
"

# Run pending migrations (no-op on fresh DB since we stamped head)
alembic upgrade head

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
