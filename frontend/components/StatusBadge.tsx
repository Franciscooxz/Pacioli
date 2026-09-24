const STYLES: Record<string, string> = {
  POSTED: "bg-success/10 text-success",
  PENDING_REVIEW: "bg-warning/15 text-[#B58500]",
  CLASSIFIED: "bg-primary/10 text-primary",
  RECEIVED: "bg-line text-ink-muted",
  PARSED: "bg-line text-ink-muted",
  REJECTED: "bg-danger/10 text-danger",
  PARSE_FAILED: "bg-danger/10 text-danger",
  POSTING_FAILED: "bg-danger/10 text-danger",
};

const LABEL: Record<string, string> = {
  RECEIVED: "Recibido",
  PARSED: "Parseado",
  CLASSIFIED: "Clasificado",
  PENDING_REVIEW: "En revisión",
  POSTED: "Contabilizado",
  PARSE_FAILED: "Parseo falló",
  POSTING_FAILED: "Posteo falló",
  REJECTED: "Rechazado",
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-bold ${
        STYLES[status] ?? "bg-line text-ink-muted"
      }`}
    >
      {LABEL[status] ?? status}
    </span>
  );
}
