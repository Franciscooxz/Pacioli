# CLAUDE.md — Contexto permanente del proyecto

> Este archivo va en la raíz del repositorio. Claude Code lo lee automáticamente
> en cada sesión. Contiene las reglas que NUNCA deben violarse.

---

## 1. Qué estamos construyendo

**Nombre provisional:** `contaflow` (cámbialo si tienes uno mejor)

Una plataforma SaaS de **automatización contable para firmas contables colombianas**.

El producto NO es un ERP ni un motor contable nuevo. Es la **capa de automatización
que se monta sobre Odoo**: captura facturas electrónicas, las clasifica, propone
asientos contables y los envía a Odoo vía su API externa.

**Cliente objetivo:** firmas contables pequeñas (3-10 personas) que manejan entre
40 y 80 empresas cliente y hoy digitan facturas a mano.

**Propuesta de valor:** reducir de horas a minutos el tiempo de registro contable,
manteniendo trazabilidad completa y control humano sobre lo ambiguo.

---

## 2. Contexto regulatorio colombiano (crítico para el diseño)

- La **factura electrónica** en Colombia es un **XML UBL 2.1** firmado digitalmente
  (XAdES-EPES). Los datos llegan **estructurados**: no se necesita OCR para el flujo
  principal.
- Cada documento tiene un **CUFE** (Código Único de Facturación Electrónica), un hash
  de 96 caracteres que lo identifica de forma única e inmutable ante la DIAN.
  **El CUFE es nuestra clave de idempotencia en todo el sistema.**
- Los proveedores están obligados a enviar la factura al correo del adquiriente con
  el XML adjunto. **Esa es nuestra vía de ingesta principal (IMAP).**
- Documentos que manejamos: `FACTURA_VENTA`, `FACTURA_COMPRA`, `NOTA_CREDITO`,
  `NOTA_DEBITO`, `DOCUMENTO_SOPORTE` (compras a no obligados a facturar),
  `NOMINA_ELECTRONICA`.
- Impuestos relevantes: IVA (0%, 5%, 19%), Retefuente, ReteIVA, ReteICA.
  El ICA varía por municipio — el modelo de datos debe soportarlo desde el inicio.
- El PUC (Plan Único de Cuentas, Decreto 2650) es jerárquico: clase (1 dígito) →
  grupo (2) → cuenta (4) → subcuenta (6) → auxiliar (7+). Solo las hojas reciben
  movimiento.

**Disclaimer legal obligatorio en toda salida del producto:** la información procesada
no reemplaza asesoría contable profesional. La responsabilidad profesional es del
contador público.

---

## 3. Stack obligatorio

| Capa | Tecnología | Nota |
|---|---|---|
| Lenguaje | **Python 3.12+** | tipado estricto, `from __future__ import annotations` |
| API | **FastAPI** + Pydantic v2 | |
| ORM | **SQLAlchemy 2.0** (estilo declarativo nuevo) + **Alembic** | |
| Base de datos | **PostgreSQL 16** | la nuestra, separada de la de Odoo |
| Cola | **Celery 5** + **Redis** | toda ingesta y clasificación es asíncrona |
| Almacenamiento | **MinIO** (S3-compatible) | XML y PDF originales, nunca en la BD |
| Motor contable | **Odoo 17 Community** + `l10n_co` (OCA) | vía XML-RPC / JSON-RPC |
| Parsing XML | **lxml** | NUNCA `xml.etree` (vulnerable a XXE) |
| Tests | **pytest** + `pytest-asyncio` + `testcontainers` | |
| Formato/lint | **ruff** (format + lint) + **mypy** en modo strict | |
| Gestor de paquetes | **uv** | |
| Frontend (fase posterior) | Next.js 15 + TypeScript + Tailwind | no empezar aún |
| Desarrollo local | **docker-compose** | Kubernetes está prohibido en esta etapa |

---

## 4. Reglas técnicas NO NEGOCIABLES

Estas reglas existen porque violarlas produce errores contables reales.
Si una instrucción mía las contradice, **detente y avísame** antes de escribir código.

### 4.1 Dinero
- **Todo valor monetario usa `Decimal` en Python y `NUMERIC(19,2)` en PostgreSQL.**
- **`float` está prohibido para dinero.** Ni en cálculos, ni en JSON, ni en tests.
- En Pydantic: `condecimal(max_digits=19, decimal_places=2)`.
- Redondeo: siempre `ROUND_HALF_UP`, nunca el banker's rounding por defecto de Python.

### 4.2 Idempotencia
- El **CUFE** tiene `UNIQUE` a nivel de base de datos, no solo validación en la app.
- Antes de crear cualquier asiento en Odoo, buscar si ya existe un `account.move`
  con ese CUFE en el campo `ref`.
- Toda tarea de Celery debe poder reejecutarse sin producir duplicados.

### 4.3 Inmutabilidad del ledger
- Un asiento contabilizado **jamás se edita ni se borra**. Se corrige con un asiento
  reverso.
- Nuestras tablas de documentos son **append-only**: los cambios de estado se registran
  en una tabla de eventos, no sobrescribiendo campos.

### 4.4 Integración con Odoo
- **Prohibido escribir SQL directo contra la base de datos de Odoo.** Siempre vía
  `execute_kw`. Escribir directo rompe el ORM, los constraints y los hooks contables.
- Crear siempre en **borrador** (`draft`), contabilizar (`action_post`) en un paso
  separado y explícito.
- Toda llamada a Odoo va envuelta en reintentos con backoff exponencial.

### 4.5 Seguridad y datos
- **Multi-tenant estricto:** cada firma contable ve solo sus empresas. Toda consulta
  filtra por `tenant_id`. Escribir un test que lo verifique por cada endpoint.
- Nunca loguear XML completos, NITs de personas naturales ni datos de nómina.
- El XML crudo se guarda **siempre**, tal cual llegó, antes de parsearlo. Es la
  evidencia ante una auditoría de la DIAN.
- Parsing de XML con `lxml` y `resolve_entities=False` para evitar XXE.

### 4.6 Asincronía
- Ningún request HTTP puede parsear un XML, llamar a Odoo o leer un buzón.
  Todo eso va a Celery. El endpoint encola y devuelve `202 Accepted`.

---

## 5. Estructura del repositorio

```
contaflow/
├── CLAUDE.md
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── alembic/
│   └── versions/
├── src/
│   └── contaflow/
│       ├── __init__.py
│       ├── config.py              # Pydantic Settings
│       ├── db.py                  # engine, sessionmaker
│       ├── models/                # SQLAlchemy
│       │   ├── tenant.py
│       │   ├── company.py         # empresas cliente de la firma
│       │   ├── source_document.py
│       │   ├── document_event.py  # append-only
│       │   └── rule.py            # reglas de clasificación
│       ├── schemas/               # Pydantic (entrada/salida API)
│       ├── ingestion/
│       │   ├── imap_reader.py
│       │   ├── ubl_parser.py
│       │   └── storage.py         # MinIO
│       ├── classification/
│       │   ├── rule_engine.py
│       │   └── ml_model.py        # fase posterior
│       ├── odoo/
│       │   ├── client.py          # wrapper XML-RPC
│       │   └── posting.py         # creación de account.move
│       ├── api/
│       │   ├── deps.py
│       │   └── routers/
│       ├── workers/
│       │   ├── celery_app.py
│       │   └── tasks.py
│       └── core/
│           ├── money.py           # helpers Decimal
│           └── exceptions.py
└── tests/
    ├── conftest.py
    ├── fixtures/xml/              # facturas UBL reales anonimizadas
    ├── unit/
    └── integration/
```

---

## 6. Modelo de datos (nuestra base, no la de Odoo)

Entidades mínimas:

- **`tenant`** — la firma contable (nuestro cliente que paga).
- **`company`** — cada empresa cliente de la firma. Tiene NIT, credenciales de Odoo
  (cifradas), buzón IMAP asociado.
- **`source_document`** — el documento tal como llegó. Campos clave:
  `cufe UNIQUE`, `doc_type`, `issuer_nit`, `issue_date`, `total NUMERIC(19,2)`,
  `raw_xml_uri` (MinIO), `status`, `company_id`, `received_at`.
- **`document_event`** — append-only. `document_id`, `event_type`, `payload JSONB`,
  `actor` (`SYSTEM` / `RULE_ENGINE` / user_id), `created_at`.
- **`classification_rule`** — `company_id`, `issuer_nit`, `match_pattern`,
  `account_code`, `cost_center`, `priority`, `confidence`.
- **`posting`** — enlace entre nuestro documento y el `account.move` de Odoo:
  `document_id`, `odoo_move_id`, `posted_at`, `reversed_by`.

Estados de `source_document`:
`RECEIVED → PARSED → CLASSIFIED → PENDING_REVIEW → POSTED`
con ramas de error: `PARSE_FAILED`, `POSTING_FAILED`, `REJECTED`.

---

## 7. Cómo quiero que trabajes

1. **Pregunta antes de asumir.** Si una decisión de diseño tiene más de una opción
   razonable, propón 2-3 con sus trade-offs y espera mi respuesta. No elijas por mí
   en decisiones estructurales.
2. **Incrementos pequeños.** Un módulo funcional y probado a la vez. No generes
   veinte archivos de golpe.
3. **Tests primero en la lógica de dominio.** Parser UBL, motor de reglas y cálculos
   monetarios se escriben con el test antes que la implementación.
4. **Explícame el porqué.** Soy desarrollador aprendiendo full stack a fondo: cuando
   uses un patrón no obvio (unit of work, outbox, backoff, etc.), dedica dos líneas
   a explicar qué problema resuelve.
5. **No inventes APIs.** Si no estás seguro de la firma exacta de un método de Odoo
   o de un campo de UBL 2.1, dilo explícitamente y sugiere cómo verificarlo.
   Prefiero un "no lo sé" a un método que no existe.
6. **Commits atómicos** con mensajes en imperativo y en español.
7. **Nada de `TODO` silenciosos.** Si dejas algo incompleto, ponlo en un archivo
   `PENDIENTES.md` con su razón.

---

## 8. Fuera de alcance por ahora

No implementes nada de esto sin que yo lo pida explícitamente:

- Frontend (Next.js) — fase 4.
- Modelos de machine learning — primero el motor de reglas, que resuelve el 70-80%.
- Cualquier llamada a un LLM — fase 5, y solo para el residuo ambiguo.
- Emisión de facturas electrónicas (requiere habilitación ante la DIAN).
- Kubernetes, Terraform, CI/CD complejo.
- Módulo de nómina.
