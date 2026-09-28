import Link from "next/link";

export default function NotFound() {
  return (
    <div className="grid min-h-screen place-items-center bg-canvas p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 text-center shadow-card">
        <div className="text-5xl font-extrabold text-primary">404</div>
        <h1 className="mt-3 text-xl font-extrabold text-ink">Página no encontrada</h1>
        <p className="mt-2 text-sm text-ink-muted">
          La página que buscas no existe o fue movida.
        </p>
        <Link
          href="/dashboard"
          className="mt-6 inline-block rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white transition hover:bg-primary-hover"
        >
          Volver al inicio
        </Link>
      </div>
    </div>
  );
}
