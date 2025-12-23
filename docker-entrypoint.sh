#!/bin/sh
set -e

if [ -n "$STARTUP_DELAY" ]; then
  echo "Startup delay set to ${STARTUP_DELAY}s"
  sleep "$STARTUP_DELAY"
fi

exec "$@"

