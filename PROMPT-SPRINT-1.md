# Prompt — Sprint 1: esqueleto e ingesta

> Pega esto en Claude Code **después** de haber puesto `CLAUDE.md` en la raíz del
> repositorio vacío. Este es el primer mensaje de la sesión.

---

Hola. Vamos a arrancar el proyecto descrito en `CLAUDE.md`. Léelo completo antes de
hacer nada y confírmame que entendiste el alcance y las reglas no negociables.

Trabajaremos en **cuatro entregas**. No avances a la siguiente hasta que yo te diga
que la anterior está aprobada. Al terminar cada una, dime exactamente qué comando debo
correr para verificarla.

---

## Entrega 1 — Andamiaje ejecutable

Objetivo: que `docker compose up` levante todo y que `pytest` corra en verde, aunque
no haya lógica todavía.

Necesito:

- `pyproject.toml` gestionado con `uv`, con las dependencias del stack de `CLAUDE.md`,
  y configuración de `ruff` (format + lint) y `mypy` en modo strict.
- `docker-compose.yml` con estos servicios, con healthchecks y volúmenes nombrados:
  - `postgres` (nuestra base, puerto 5432)
  - `redis`
  - `minio` (consola incluida)
  - `api` (FastAPI con hot reload)
  - `worker` (Celery)
  - `odoo` + `odoo-db` (Postgres separado — **no compartir base con la nuestra**)
- `src/contaflow/config.py` con Pydantic Settings leyendo de variables de entorno,
  y `.env.example` documentado.
- `src/contaflow/db.py` con engine async de SQLAlchemy 2.0 y sessionmaker.
- Alembic inicializado y apuntando a nuestra base.
- Un endpoint `GET /health` que verifique conectividad real con Postgres, Redis y MinIO
  y devuelva el estado de cada uno.
- `pytest` configurado con un test que valide que `/health` responde 200.
- `Makefile` con: `make up`, `make down`, `make test`, `make lint`, `make migrate`.

Antes de escribir código, muéstrame el `docker-compose.yml` propuesto y espera mi visto
bueno. Ahí es donde más fácil se cometen errores difíciles de deshacer.

---

## Entrega 2 — Modelo de datos y migraciones

Implementa los modelos SQLAlchemy descritos en la sección 6 de `CLAUDE.md`.

Requisitos específicos:

- Todos los montos en `NUMERIC(19,2)`, mapeados a `Decimal` en Python.
- `UNIQUE` real sobre `cufe` a nivel de base de datos.
- `CHECK` que impida `total < 0` en documentos (las notas crédito se modelan con
  `doc_type`, no con montos negativos).
- Índices pensados para las consultas reales: por `(company_id, status)`,
  por `(company_id, issue_date)`, por `issuer_nit`.
- `document_event` es append-only: ponle un trigger de PostgreSQL que rechace
  `UPDATE` y `DELETE` sobre esa tabla.
- Todas las tablas multi-tenant llevan `tenant_id` con foreign key.
- Enums de Python mapeados a tipos `ENUM` nativos de PostgreSQL, no a `VARCHAR`.
- Migración de Alembic generada y revisada a mano (las autogeneradas siempre traen
  ruido — muéstramela antes de aplicarla).

Incluye tests con `testcontainers` que verifiquen:
- que insertar dos documentos con el mismo CUFE falla;
- que un `UPDATE` sobre `document_event` falla;
- que los `Decimal` sobreviven el round-trip sin perder precisión.

---

## Entrega 3 — Parser UBL 2.1

Este es el módulo más delicado del sprint. **Escribe los tests primero.**

`src/contaflow/ingestion/ubl_parser.py` debe exponer:

```python
def parse_ubl(xml_bytes: bytes) -> ParsedDocument: ...
```

Donde `ParsedDocument` es un modelo Pydantic con: `cufe`, `document_number`,
`doc_type`, `issue_date`, `issuer_nit`, `issuer_name`, `receiver_nit`, `currency`,
`subtotal`, `total_tax`, `total`, `taxes: list[TaxDetail]`, `lines: list[DocumentLine]`.

Requisitos:

- Namespaces UBL 2.1 correctos (`cbc`, `cac`, `ext`, `sts` para la extensión DIAN).
- Manejar el caso del **`AttachedDocument`**: muchos proveedores envían un XML
  contenedor con la factura real embebida como CDATA dentro de
  `cac:Attachment/cac:ExternalReference/cbc:Description`. Hay que detectarlo y
  desanidar antes de parsear.
- Soportar `Invoice`, `CreditNote` y `DebitNote` como raíces distintas.
- Todos los montos como `Decimal`, nunca `float`.
- Parsing seguro contra XXE: sin resolución de entidades, sin acceso a red.
- Errores tipados y específicos (`MissingCufeError`, `UnsupportedDocumentTypeError`,
  `MalformedUblError`), nunca un `except Exception` genérico.
- **Validación de consistencia:** si `subtotal + total_tax != total`, no falles
  silenciosamente — marca el documento con una advertencia explícita en el resultado.

Para los tests necesito fixtures en `tests/fixtures/xml/`. Genera tú mismo 5 XMLs
sintéticos que cubran: factura simple, factura con varias tarifas de IVA, nota crédito,
`AttachedDocument` anidado, y un XML corrupto. **Anonimiza todo dato.**

No implementes la validación de la firma digital XAdES todavía — déjalo anotado en
`PENDIENTES.md` con una explicación de por qué importa.

---

## Entrega 4 — Lector IMAP y pipeline de ingesta

`src/contaflow/ingestion/imap_reader.py` + la tarea de Celery que lo orquesta.

Flujo completo:

1. Tarea periódica de Celery Beat que recorre las `company` activas.
2. Por cada una, conecta al buzón IMAP (IMAP4_SSL) y busca correos no procesados.
3. Extrae adjuntos: XML directos y XML dentro de ZIP (es muy común que vengan
   comprimidos junto al PDF).
4. **Antes de parsear**, sube el archivo crudo a MinIO y crea el `source_document`
   en estado `RECEIVED` con el `raw_xml_uri`.
5. Encola la tarea de parsing. Si tiene éxito → `PARSED`; si falla → `PARSE_FAILED`
   con el error registrado en `document_event`.
6. Marca el correo como leído solo después de que el documento esté persistido.

Requisitos:

- Idempotencia total: si la tarea corre dos veces sobre el mismo correo, no se duplica
  nada. Verifícalo con un test.
- Reintentos con backoff exponencial y un límite claro; después va a una cola de
  fallidos, no se pierde.
- Límite de tamaño de adjunto y validación de que el ZIP no sea una zip bomb.
- No loguear nunca el contenido del XML ni direcciones de correo completas.
- Tests de integración con un servidor IMAP falso (`aioimaplib` mockeado o un
  contenedor de `greenmail`) — propón tú la opción más simple y justifícala.

---

## Al terminar

Escribe un `README.md` con: cómo levantar el entorno desde cero, cómo cargar una
factura de prueba, y un diagrama en Mermaid del flujo de ingesta.

Y dime honestamente qué partes te parecen frágiles o qué decisiones tomaste con
información incompleta.
