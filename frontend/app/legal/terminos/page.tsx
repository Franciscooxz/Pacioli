import Link from "next/link";

export const metadata = {
  title: "Términos y condiciones — Contaflow",
};

export default function TerminosPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <Link href="/login" className="text-sm font-semibold text-primary hover:underline">
        ← Volver
      </Link>

      <div className="mt-4 rounded-2xl bg-white p-8 shadow-card">
        <h1 className="text-2xl font-extrabold text-ink">Términos y condiciones de uso</h1>
        <p className="mt-2 rounded-lg bg-warning/10 px-3 py-2 text-sm font-medium text-[#8a6d00]">
          Borrador. Este texto es una base y debe revisarse con un abogado antes de publicarse.
        </p>

        <div className="mt-6 space-y-6 text-sm leading-relaxed text-ink">
          <section>
            <h2 className="text-base font-bold">1. Objeto</h2>
            <p className="mt-1 text-ink-muted">
              Contaflow es una plataforma de automatización contable que captura documentos
              electrónicos, los clasifica y propone/registra asientos en el sistema contable de la
              firma. El servicio se presta &quot;tal cual&quot;, sujeto a estos términos.
            </p>
          </section>

          <section>
            <h2 className="text-base font-bold">2. Cuenta y responsabilidad del usuario</h2>
            <p className="mt-1 text-ink-muted">
              El usuario es responsable de la confidencialidad de sus credenciales y de la
              veracidad de la información y credenciales (Odoo, correo) que cargue. Debe usar el
              servicio conforme a la ley.
            </p>
          </section>

          <section>
            <h2 className="text-base font-bold">3. Propiedad intelectual</h2>
            <p className="mt-1 text-ink-muted">
              El software, la marca y el contenido de la plataforma pertenecen a su titular. Los
              datos y documentos de cada firma siguen siendo de la firma.
            </p>
          </section>

          <section>
            <h2 className="text-base font-bold">4. Naturaleza contable del servicio</h2>
            <p className="mt-1 text-ink-muted">
              La información procesada por Contaflow <strong>no reemplaza la asesoría contable
              profesional</strong>. La responsabilidad profesional sobre los registros contables y
              tributarios recae en el contador público a cargo. El usuario debe revisar y aprobar
              los asientos antes de contabilizarlos.
            </p>
          </section>

          <section>
            <h2 className="text-base font-bold">5. Limitación de responsabilidad</h2>
            <p className="mt-1 text-ink-muted">
              En la medida permitida por la ley, no respondemos por daños indirectos derivados del
              uso del servicio, ni por errores originados en datos incorrectos suministrados por el
              usuario o por terceros (proveedores, DIAN, Odoo).
            </p>
          </section>

          <section>
            <h2 className="text-base font-bold">6. Datos personales</h2>
            <p className="mt-1 text-ink-muted">
              El tratamiento de datos se rige por la{" "}
              <Link href="/legal/privacidad" className="font-semibold text-primary hover:underline">
                política de privacidad
              </Link>
              .
            </p>
          </section>

          <section>
            <h2 className="text-base font-bold">7. Modificaciones y ley aplicable</h2>
            <p className="mt-1 text-ink-muted">
              Podemos actualizar estos términos. Se rigen por las leyes de la República de Colombia.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
