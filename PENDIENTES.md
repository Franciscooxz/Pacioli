# PENDIENTES

Cosas dejadas conscientemente incompletas, con su razon. No son bugs: son alcance
diferido a proposito.

## Validacion de la firma digital XAdES-EPES (Entrega 3)

**Qué falta:** el parser (`src/contaflow/ingestion/ubl_parser.py`) extrae los datos del
XML pero **no verifica la firma digital XAdES-EPES** que la DIAN exige en la factura
electronica.

**Por qué importa:** la firma es lo que prueba que el documento (a) fue emitido por
quien dice el NIT y (b) no fue alterado despues de firmarse. Sin validarla, un XML bien
formado pero falsificado pasaria el parseo. El CUFE nos da idempotencia, no
autenticidad; la firma da autenticidad e integridad.

**Por qué se difiere:** validar XAdES correctamente implica (1) parsear la extension
`ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/ds:Signature`, (2) verificar
la cadena de certificados contra las CA acreditadas en Colombia, (3) validar el sello
de tiempo y la politica de firma EPES, y (4) recalcular los digests de las referencias
firmadas. Es un modulo en si mismo (probablemente con `signxml` o `xmlsec`) y no debe
mezclarse con la extraccion de datos.

**Cómo abordarlo cuando toque:**
- Modulo aparte, p. ej. `src/contaflow/ingestion/signature.py`, con
  `verify_xades(xml_bytes) -> SignatureResult`.
- Evaluar `xmlsec` (bindings de libxmlsec1) o `signxml`. Verificar que soporten
  XAdES-EPES, no solo XML-DSig basico.
- Conseguir la lista de CA raiz acreditadas (ONAC / entidades de certificacion).
- El pipeline de ingesta deberia guardar el resultado de la verificacion como un
  `document_event` y, si falla, mandar el documento a revision (no descartarlo en
  silencio).

## Cola de fallidos / dead-letter (Entrega 4)

**Qué falta:** hay dos niveles de fallo que hoy no van a una verdadera cola de fallidos:
- **A nivel de tarea:** `parse_document` e `ingest_company` reintentan con backoff
  exponencial (`autoretry_for` transitorios, `max_retries=5`). Al agotar reintentos, la
  tarea falla y su resultado queda en el backend de Redis, pero no hay un DLQ formal.
- **A nivel de correo:** si `extract_xml_attachments` falla (correo roto o zip bomb),
  hoy se marca el correo como leido para no reprocesar en bucle y se loguea, pero el
  correo no se guarda en ninguna parte para inspeccion posterior.

**Cómo abordarlo:** una tabla `ingestion_failure` (o un topic/cola dedicada) que guarde
el origen (uid del correo, company), el motivo y, para el caso de correo, el crudo del
adjunto en MinIO. Redis como broker no tiene dead-letter nativo; se puede emular con una
cola dedicada + un handler `on_failure` en las tareas.

## Fixtures UBL sinteticos (Entrega 3)

Los XML de `tests/fixtures/xml/` son **sinteticos y anonimizados**, reconstruidos segun
la estructura estandar UBL 2.1 / DIAN. Detalles a validar contra facturas reales:
`schemeName` del CUFE/CUDE, los codigos exactos de `InvoiceTypeCode` para Documento
Soporte, y el mapeo por nombre de las retenciones (`_tax_category` en el parser).

## Municipio del ICA/ReteICA (Fase 1.5)

El modelo (`document_tax.municipality`) y el schema (`TaxDetail.municipality`) ya
soportan el municipio, pero el parser aun NO lo extrae del XML (queda en None): no
tenemos claro en que elemento UBL lo pone la DIAN. Validar con una factura real con
ReteICA y completar la extraccion. El ICA varia por municipio, asi que esto importa para
liquidar y reportar bien.

## Posting a Odoo real (Fase 3b)

La logica de posting esta hecha y probada con un OdooClient falso, PERO no se ha
verificado contra un Odoo real. Falta (necesita tu entorno):

- **Configurar Odoo:** crear la base, instalar `l10n_co` (OCA) en `odoo/addons/`, cargar
  el PUC, crear el diario de compras y un usuario/API key por empresa.
- **Guardar credenciales** de Odoo en `company` (odoo_url, odoo_db, odoo_username,
  odoo_password cifrada) y el `posting_config` (codigos de cuenta: payable, iva,
  retefuente, reteiva, reteica).
- **Verificar las firmas de `execute_kw`** en `odoo/client.py` contra Odoo 17 real:
  nombres de campos de `account.move` (move_type "entry", line_ids), `account.account`
  (code), `res.partner` (vat), `account.journal` (type "purchase"). Ver rule #5.
- **Ventas y notas ya implementadas (Fase B):** FACTURA_VENTA arma el asiento espejo
  (CxC + retenciones a favor = ingreso + IVA generado) y las notas resuelven su lado por
  NIT (NOTA_CREDITO invierte el asiento). Falta VERIFICAR contra Odoo real: que exista el
  diario de ventas (`type = "sale"`) y agregar al `posting_config` las cuentas del lado
  venta (`receivable`, `iva_generado`, `retefuente_favor`, `reteiva_favor`,
  `reteica_favor`). Probado solo con OdooClient falso.
- **Dinero -> float** solo en el borde XML-RPC (Odoo no acepta Decimal); documentado en
  `_to_odoo_amount`.

## Nomina y moneda extranjera (Fase C)

- `NOMINA_ELECTRONICA`: **parseo ligero implementado** (raiz `NominaIndividual`: CUNE,
  empleador, trabajador, totales devengados/deducciones/comprobante). Se ingesta como
  evidencia pero NO se contabiliza (CLAUDE.md §8 excluye el modulo de nomina). Falta
  VERIFICAR las rutas/atributos del esquema DIAN contra una nomina real (hoy el fixture
  `nomina_simple.xml` es sintetico): `InformacionGeneral@CUNE/@FechaGen/@TipoMoneda`,
  `Empleador@NIT`, `NumeroSecuenciaXML@Numero` y si los totales son elemento o atributo.
  `NominaIndividualDeAjuste` se enruta igual pero no se ha probado.

- Moneda extranjera / TRM: **implementado** con la TRM del XML (`cac:PaymentExchangeRate`)
  y conversion a COP al contabilizar. Falta la **fuente oficial de TRM** (Fase F) para los
  documentos que no la traen en el XML: implementar un `TrmProvider` real
  (Superfinanciera / datos abiertos) e inyectarlo en `post_document`.
