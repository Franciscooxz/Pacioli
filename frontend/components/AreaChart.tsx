// Grafico de area/linea hecho a mano con SVG (sin librerias). Escala al ancho del
// contenedor manteniendo el viewBox 900x260.

interface Point {
  label: string;
  value: number;
}

export default function AreaChart({ data }: { data: Point[] }) {
  const w = 900;
  const h = 260;
  const padX = 24;
  const padY = 24;

  if (data.length === 0) {
    return (
      <div className="grid h-[220px] place-items-center text-sm text-ink-muted">Sin datos aun</div>
    );
  }

  const max = Math.max(...data.map((d) => d.value), 1);
  const stepX = (w - padX * 2) / Math.max(data.length - 1, 1);
  const px = (i: number) => padX + i * stepX;
  const py = (v: number) => h - padY - (v / max) * (h - padY * 2);

  const pts = data.map((d, i) => `${px(i)},${py(d.value)}`);
  const line = `M ${pts.join(" L ")}`;
  const area = `M ${px(0)},${h - padY} L ${pts.join(" L ")} L ${px(data.length - 1)},${h - padY} Z`;
  const grid = [0, 0.25, 0.5, 0.75, 1];

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-auto w-full">
      <defs>
        <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#4880FF" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#4880FF" stopOpacity="0" />
        </linearGradient>
      </defs>
      {grid.map((g) => {
        const y = padY + g * (h - padY * 2);
        return <line key={g} x1={padX} x2={w - padX} y1={y} y2={y} stroke="#EEF0F4" strokeWidth={1} />;
      })}
      <path d={area} fill="url(#areaFill)" />
      <path d={line} fill="none" stroke="#4880FF" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
      {data.map((d, i) => (
        <circle key={i} cx={px(i)} cy={py(d.value)} r={3.5} fill="#fff" stroke="#4880FF" strokeWidth={2} />
      ))}
    </svg>
  );
}
