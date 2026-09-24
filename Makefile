.PHONY: up down test lint migrate revision logs fmt

# Levanta todo el stack (reconstruye imagenes si cambiaron).
up:
	docker compose up -d --build

# Detiene y elimina contenedores (conserva los volumenes).
down:
	docker compose down

# Tests unitarios en un contenedor efimero (las sondas se mockean, --no-deps evita
# levantar postgres/redis/minio). No requiere uv en el host.
test:
	docker compose run --rm --no-deps api uv run pytest tests/unit

# Tests de integracion: usan testcontainers, que necesita hablar con el Docker del
# host, por eso corren con uv en el host (no dentro de un contenedor). Requiere uv.
test-int:
	uv run --python 3.12 pytest tests/integration

# Lint + formato + tipos, dentro del contenedor.
lint:
	docker compose run --rm --no-deps api uv run ruff check .
	docker compose run --rm --no-deps api uv run ruff format --check .
	docker compose run --rm --no-deps api uv run mypy

# Autoformatea el codigo, dentro del contenedor.
fmt:
	docker compose run --rm --no-deps api uv run ruff format .
	docker compose run --rm --no-deps api uv run ruff check --fix .

# Aplica migraciones dentro del contenedor api (usa la red interna de docker).
migrate:
	docker compose run --rm api alembic upgrade head

# Genera una migracion autogenerada. Uso: make revision m="mensaje"
revision:
	docker compose run --rm api alembic revision --autogenerate -m "$(m)"

# Logs en vivo de api y worker.
logs:
	docker compose logs -f api worker
