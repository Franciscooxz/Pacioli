# Imagen para los servicios api y worker. Usa uv como gestor de paquetes.
FROM python:3.12-slim

# uv oficial, version fijada para reproducibilidad.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Copiamos metadatos primero para aprovechar cache de capas.
COPY pyproject.toml README.md ./
COPY src ./src

# Instala dependencias + el proyecto (editable) en /app/.venv.
# El montaje de ./src en docker-compose habilita el hot reload sobre este layout.
RUN uv sync

EXPOSE 8000
