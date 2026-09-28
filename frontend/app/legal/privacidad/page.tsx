import Link from "next/link";

export const metadata = {
  title: "Política de privacidad — Contaflow",
};

export default function PrivacidadPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <Link href="/login" className="text-sm font-semibold text-primary hover:underline">
        ← Volver
      </Link>

      <div className="mt-4 rounded-2xl bg-white p-8 shadow-card">
        <h1 className="text-2xl font-extrabold text-ink">Política de tratamiento de datos personales</h1>
        <p className="mt-2 rounded-lg bg-warning/10 px-3 py-2 text-sm font-medium text-[#8a6d00]">
          Borrador. Este texto es una base y debe revisarse con un abogado antes de publicarse.
          Marco: Ley 1581 de 2012 y Decreto 1377 de 2013 (Colombia).
        </p>

        <div className="mt-6 space-y-6 text-sm leading-relaxed text-ink">
          <section>
            <h2 className="text-base font-bold">1. Responsable</h2>
            <p className="mt-1 text-ink-muted">
              [Razón social de la firma], NIT [___], con domicilio en [___], correo
              [privacidad@tu-dominio.co]. Contaflow es la plataforma que la firma usa para
              automatizar su contabilidad.
            </p>
          </section>

          <section>
            <h2 className="text-base font-bold">2. Datos que tratamos</h2>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-ink-muted">
              <li>De los usuarios de la firma: nombre, correo electrónico y credenciales de acceso.</li>
              <li>
                De las empresas cliente: NIT, razón social y credenciales de Odoo/IMAP
                (almacenadas cifradas en reposo).
              </li>
              <li>
                De los documentos electrónicos: facturas UBL (emisor, NIT, montos, CUFE),
                notas y nómina electrónica, junto con el XML original como evidencia ante la DIAN.
              </li>
              <li>Datos técnicos: direcciones IP y registros (logs) de uso para seguridad.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-bold">3. Finalidad</h2>
            <p className="mt-1 text-ink-muted">
              Recibir, clasificar y contabilizar documentos electrónicos en el sistema contable
              (Odoo) de cada empresa cliente, con trazabilidad y control humano. No usamos los
              datos para fines distintos sin autorización.
            </p>
          </section>

          <section>
            <h2 className="text-base font-bold">4. Almacenamiento y seguridad</h2>
            <p className="mt-1 text-ink-muted">
              Los datos se guardan en bases de datos y almacenamiento de objetos con controles de
              acceso. Las credenciales sensibles se cifran. El acceso está segregado por firma
              (multi-tenant): cada firma solo ve sus empresas.
            </p>
          </section>

          <section>
            <h2 className="text-base font-bold">5. Derechos del titular (Ley 1581)</h2>
            <p className="mt-1 text-ink-muted">
              Como titular puedes conocer, actualizar y rectificar tus datos; solicitar prueba de
              la autorización; ser informado del uso; presentar quejas ante la SIC; revocar la
              autorización y solicitar la supresión cuando proceda. Para ejercerlos, escribe a
              [privacidad@tu-dominio.co].
            </p>
          </section>

          <section>
            <h2 className="text-base font-bold">6. Conservación</h2>
            <p className="mt-1 text-ink-muted">
              Conservamos los datos mientras exista la relación con la firma y por los plazos que
              exija la ley contable y tributaria colombiana. El XML de las facturas se conserva como
              evidencia de auditoría.
            </p>
          </section>

          <section>
            <h2 className="text-base font-bold">7. Vigencia</h2>
            <p className="mt-1 text-ink-muted">Esta política rige desde [fecha] y puede actualizarse.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
