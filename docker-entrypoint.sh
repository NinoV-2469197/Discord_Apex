#!/bin/sh
set -e

echo "=== Entrypoint Script Started ==="
echo "APP_DIR: ${APP_DIR}"

# Map Railway variables to expected variable names based on APP_DIR
if [ -z "$DISCORD_BOT_TOKEN" ]; then
  case "$APP_DIR" in
    apex)
      echo "Mapping variables for apex (map bot)..."
      if [ -n "$DISCORD_BOT_TOKEN_MAP" ]; then
        export DISCORD_BOT_TOKEN="$DISCORD_BOT_TOKEN_MAP"
        echo "Mapped DISCORD_BOT_TOKEN_MAP to DISCORD_BOT_TOKEN"
      else
        echo "WARNING: DISCORD_BOT_TOKEN_MAP not set"
      fi
      ;;
    apex_daan)
      echo "Mapping variables for apex_daan..."
      if [ -n "$DISCORD_BOT_TOKEN_DAAN" ]; then
        export DISCORD_BOT_TOKEN="$DISCORD_BOT_TOKEN_DAAN"
        echo "Mapped DISCORD_BOT_TOKEN_DAAN to DISCORD_BOT_TOKEN"
      else
        echo "WARNING: DISCORD_BOT_TOKEN_DAAN not set"
      fi
      if [ -n "$PLAYER_UID_DAAN" ]; then
        export PLAYER_UID="$PLAYER_UID_DAAN"
        echo "Mapped PLAYER_UID_DAAN to PLAYER_UID"
      else
        echo "WARNING: PLAYER_UID_DAAN not set"
      fi
      ;;
    apex_eben)
      echo "Mapping variables for apex_eben..."
      if [ -n "$DISCORD_BOT_TOKEN_EBEN" ]; then
        export DISCORD_BOT_TOKEN="$DISCORD_BOT_TOKEN_EBEN"
        echo "Mapped DISCORD_BOT_TOKEN_EBEN to DISCORD_BOT_TOKEN"
      else
        echo "WARNING: DISCORD_BOT_TOKEN_EBEN not set"
      fi
      if [ -n "$PLAYER_UID_EBEN" ]; then
        export PLAYER_UID="$PLAYER_UID_EBEN"
        echo "Mapped PLAYER_UID_EBEN to PLAYER_UID"
      else
        echo "WARNING: PLAYER_UID_EBEN not set"
      fi
      ;;
    apex_nino)
      echo "Mapping variables for apex_nino..."
      if [ -n "$DISCORD_BOT_TOKEN_NINO" ]; then
        export DISCORD_BOT_TOKEN="$DISCORD_BOT_TOKEN_NINO"
        echo "Mapped DISCORD_BOT_TOKEN_NINO to DISCORD_BOT_TOKEN"
      else
        echo "WARNING: DISCORD_BOT_TOKEN_NINO not set"
      fi
      if [ -n "$PLAYER_UID_NINO" ]; then
        export PLAYER_UID="$PLAYER_UID_NINO"
        echo "Mapped PLAYER_UID_NINO to PLAYER_UID"
      else
        echo "WARNING: PLAYER_UID_NINO not set"
      fi
      ;;
    *)
      echo "WARNING: Unknown APP_DIR: ${APP_DIR}"
      ;;
  esac
else
  echo "DISCORD_BOT_TOKEN already set (from docker-compose or Railway)"
fi

if [ -n "$STARTUP_DELAY" ]; then
  echo "Startup delay set to ${STARTUP_DELAY}s"
  sleep "$STARTUP_DELAY"
  echo "Startup delay completed"
else
  echo "No STARTUP_DELAY set (using default: 0s)"
fi

echo "=== Starting Application ==="
exec "$@"

