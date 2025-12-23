# Dockerising the Apex bots

This project contains four Discord bots (`apex`, `apex_daan`, `apex_eben`, `apex_nino`).  
Each bot expects its own Discord token and Apex API credentials, so every bot is isolated in
its own container.

## 1. Prerequisites

- Docker Engine 24+ and Docker Compose Plugin v2.
- Copies of every required secret:
  - Map bot (`apex`): `DISCORD_BOT_TOKEN`, `APEX_API_KEY`.
  - Player bots (`apex_*`): `DISCORD_BOT_TOKEN`, `APEX_API_KEY`, `PLAYER_UID`.

## 2. Prepare environment files

Create one `.env` file per bot directory and place it next to the corresponding `main.py`.
Example for `apex_daan/.env`:

```
DISCORD_BOT_TOKEN=xxxx
APEX_API_KEY=yyyy
PLAYER_UID=zzzz
```

> ⚠️ Never commit these `.env` files; they stay local only.

## 3. Build and start every bot

From the project root run:

```
docker compose up --build -d
```

Compose will build the shared Python image four times (one per app directory) and start the
containers named:

- `apex-map-bot`
- `apex-daan-bot`
- `apex-eben-bot`
- `apex-nino-bot`

Each service defines a `STARTUP_DELAY` (0s, 10s, 20s, 30s respectively) so they log in
sequentially and avoid Discord rate limits. Tweak these values in `docker-compose.yml`
whenever you add/remove bots.

## 4. Managing the stack

- View logs for a specific bot:
  ```
  docker compose logs -f apex_daan_bot
  ```
- Restart a bot after changing its code:
  ```
  docker compose up --build -d apex_daan_bot
  ```
- Stop everything:
  ```
  docker compose down
  ```

## 5. Customisation tips

- To add another bot folder, duplicate one of the existing services in `docker-compose.yml`
  and change the `APP_DIR`, `container_name`, and `env_file` values.
- If you need additional Python packages for a single bot, add them to that folder’s
  `requirements.txt`; the build argument ensures each image installs only what it needs.
