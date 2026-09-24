const fmtNum = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 });

export const money = (s: string | null): string => (s == null ? "—" : `$${fmtNum.format(Number(s))}`);

export const pct = (s: string | null): number | null =>
  s == null ? null : Math.round(Number(s) * 100);
