#!/bin/sh
# Apply migrations, then start the server.
# With several replicas (Cloud Run / ECS), set RUN_MIGRATIONS=false and run
# `alembic upgrade head` as a one-off job before deploying instead.
set -e
if [ "${RUN_MIGRATIONS:-true}" != "false" ]; then
  alembic upgrade head
fi
exec "$@"
