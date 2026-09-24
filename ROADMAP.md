# ROADMAP — camino al 100%

Plan por fases para completar `contaflow`. Criterio de orden: **todo lo que se puede
construir y probar con dobles (fakes), certificados de prueba y XML sinteticos va
primero**; todo lo que necesita credenciales, APIs externas o facturas reales se agrupa
al final, en la Fase F. Asi el codigo llega al 100% sin depender de accesos externos.

Estado: [ ] pendiente · [~] en curso · [x] hecho.

---

## Fase A — Robustez del pipeline: cola de fallidos (dead-letter)  [x]

Cubre el pendiente "Cola de fallidos / dead-letter" de `PENDIENTES.md`.

- [x] Tabla `ingestion_failure` (modelo + migracion) con contexto: etapa, empresa,
      documento, motivo, `raw_uri` del crudo y `payload`. No append-only: `resolved_at`
      permite marcar un fallo como atendido sin borrar evidencia.
- [x] Fallo de correo: al no poder abrir un correo (zip bomb, etc.), `process_mailbox`
      guarda el crudo en MinIO y registra el fallo, ademas de marcarlo leido.
- [x] Fallo de tarea: `DeadLetterTask` (base de Celery) registra el fallo terminal en
      `on_failure`, tras agotar reintentos.
- [x] Tests de integracion (correo roto -> cola) y de la funcion de registro.
- [x] Verificado: ruff + mypy strict + pytest (98 tests) + migraciones aplican limpio.

## Fase B — Cobertura de asientos: ventas y notas  [x]

- [x] Asiento de `FACTURA_VENTA` (espejo de la compra): CxC + retenciones a favor =
      ingreso + IVA generado. Cuentas nuevas en `posting_config` (JSONB, sin migracion).
- [x] Notas: perspectiva compra/venta por NIT (`posting_side`), `NOTA_CREDITO` invierte
      el asiento (`reverse_lines`), `NOTA_DEBITO` va en el mismo sentido. Diario de ventas
      (`find_sale_journal_id`) o de compras segun el lado.
- [x] Helper de NIT centralizado en `core/nit.py` (lo comparten pipeline y posting).
- [x] Tests unitarios (venta balanceada, inversion, `posting_side`) y de integracion
      (venta OK, nota credito compra invertida, nota de perspectiva indeterminada).
- [x] Verificado: ruff + mypy strict + pytest (98 tests) + migraciones aplican limpio.

## Fase C — Documentos y moneda  [x]

- [x] `NOMINA_ELECTRONICA`: parseo LIGERO de la raiz `NominaIndividual` (CUNE, empleador,
      trabajador, totales). Ingesta como evidencia, sin modulo de nomina (CLAUDE.md §8):
      no se contabiliza. Rutas del esquema a validar con nomina real (PENDIENTES.md).
- [x] Moneda extranjera / TRM: `source_document.trm` (migracion), la TRM se lee del XML
      (`cac:PaymentExchangeRate`) y el posting convierte a COP con `Decimal` ROUND_HALF_UP.
      `TrmProvider` inyectable para cuando el XML no la trae; la fuente oficial va en F.
- [x] Verificado: ruff + mypy strict + pytest (98 tests) + migraciones aplican limpio.

## Fase D — Firma digital XAdES-EPES  [ ]

Cubre el pendiente de firma de `PENDIENTES.md`.

- [ ] Modulo `ingestion/signature.py` con `verify_xades(xml_bytes) -> SignatureResult`:
      parseo de `ds:Signature`, recalculo de digests. Desarrollo y prueba con
      certificados autofirmados.
- [ ] Integracion al pipeline: guardar el resultado como `document_event`; si falla,
      mandar a revision (no descartar en silencio).
- [ ] Pendiente para Fase F: cargar la cadena de CA raiz acreditadas reales.

## Fase E — Frontend (rediseño DashStack)  [~]

Diseño: DashStack (admin dashboard claro, acento #4880FF, Nunito Sans, lucide-react).
Reemplaza el "terminal financiero" anterior.

- [x] Incremento 1 — Shell + Login + Dashboard: layout con sidebar+topbar (guard de
      token), login DashStack, dashboard con stat cards + gráfico de área (SVG) + tabla
      de recientes. `next build` OK y verificado en vivo con el usuario demo.
- [x] Incremento 2 — /documents: revisión (tabla con filtros En revisión/Clasificados/
      Todos + búsqueda; panel lateral con datos, asiento propuesto y acciones aprobar /
      rechazar / contabilizar). Reemplaza la consola terminal. Typecheck OK y verificado
      en vivo (drawer con asiento correcto, acciones con enable/disable por estado).
- [ ] Incremento 3 — /rules, /companies, /failures (dead-letter).
- [ ] Menú móvil (el sidebar hoy se oculta bajo `md`).

## Fase F — Conexion con el mundo real (requiere credenciales / datos)  [ ]

Se hace al final: convierte "probado con fakes" en "funciona de verdad".

- [ ] Odoo real: montar instancia + `l10n_co`, cargar PUC, diario de compras.
- [ ] Verificar las firmas de `execute_kw` contra Odoo 17 real (rule #4.4 y #5).
- [ ] Cargar credenciales de Odoo por empresa (cifradas) y `posting_config`.
- [ ] IMAP real: conectar un buzon de verdad.
- [ ] XAdES: cargar la lista de CA raiz acreditadas (ONAC).
- [ ] Municipio del ICA/ReteICA: validar con factura real y completar la extraccion.
- [ ] Fixtures reales anonimizados en `tests/fixtures/xml/`.
- [ ] TRM: conectar la fuente oficial (Superfinanciera / datos abiertos).

### Credenciales / APIs a conseguir para la Fase F

| Que | Para que | Donde |
|---|---|---|
| Instancia Odoo 17 + `l10n_co` (OCA) | Motor contable real | self-host u Odoo.sh |
| API key + usuario Odoo por empresa | `execute_kw` autenticado | dentro de Odoo |
| Buzon IMAP (correo + app-password) | Ingesta real | correo donde llegan los XML |
| CA raiz acreditadas en Colombia | Validar XAdES | ONAC / entidades de certificacion |
| 2-3 facturas reales anonimizadas | Validar parser, ICA, fixtures | de la operacion del cliente |
| Fuente de TRM oficial | Moneda extranjera | Superfinanciera / datos abiertos |
</invoke>
