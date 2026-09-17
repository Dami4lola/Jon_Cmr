#!/bin/bash
# Bootstrap a local development database.
#
# Mirrors exactly what start.sh does on a fresh database: create the tables from the
# SQLModel metadata, then stamp alembic at head. Do NOT use `alembic upgrade head` on
# an empty database - migrations before 0014 predate the existence-guard convention in
# agents.md and will fail with "duplicate column" once create_all has run. Production
# never hits that path because start.sh stamps instead of upgrading.
set -e
cd "$(dirname "$0")/.."

# Prefer the project venv, then whatever python is on PATH. start.sh can just say
# "python" because its container has only one.
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  PY=python3
fi

"$PY" -c "
from app.database import create_db_and_tables
import app.models  # noqa: F401  - registers every table on the metadata
create_db_and_tables()
print('Tables created')
"

"$PY" -m alembic stamp head
echo "Stamped alembic at head. Local database ready."
