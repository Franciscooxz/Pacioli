"use client";

// global-error reemplaza el layout raiz cuando algo falla, por eso usa estilos inline:
// garantiza que la pagina se vea aunque el CSS no cargue.
export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="es">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif", background: "#F5F6FA" }}>
        <div style={{ display: "grid", minHeight: "100vh", placeItems: "center", padding: 16 }}>
          <div
            style={{
              maxWidth: 420,
              width: "100%",
              background: "#fff",
              borderRadius: 16,
              padding: 32,
              textAlign: "center",
              boxShadow: "0 4px 24px rgba(15,23,42,0.05)",
            }}
          >
            <div style={{ fontSize: 48, fontWeight: 800, color: "#EF3826" }}>500</div>
            <h1 style={{ marginTop: 12, fontSize: 20, fontWeight: 800, color: "#202224" }}>
              Algo salió mal
            </h1>
            <p style={{ marginTop: 8, fontSize: 14, color: "#6B7280" }}>
              Ocurrió un error inesperado. Intenta de nuevo.
            </p>
            <button
              type="button"
              onClick={() => reset()}
              style={{
                marginTop: 24,
                borderRadius: 8,
                background: "#4880FF",
                color: "#fff",
                border: 0,
                padding: "10px 20px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Reintentar
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
