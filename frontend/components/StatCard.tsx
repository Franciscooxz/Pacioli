import { ArrowDown, ArrowUp, type LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: string;
  icon: LucideIcon;
  iconBg: string;
  iconColor: string;
  trend?: { dir: "up" | "down"; text: string };
}

export default function StatCard({ label, value, icon: Icon, iconBg, iconColor, trend }: Props) {
  return (
    <div className="rounded-card bg-white p-5 shadow-card">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm font-semibold text-ink-muted">{label}</div>
          <div className="mt-2 text-3xl font-extrabold text-ink">{value}</div>
        </div>
        <span
          className="grid h-14 w-14 place-items-center rounded-2xl"
          style={{ background: iconBg }}
        >
          <Icon size={26} style={{ color: iconColor }} />
        </span>
      </div>
      {trend && (
        <div className="mt-4 flex items-center gap-1.5 text-sm">
          {trend.dir === "up" ? (
            <ArrowUp size={16} className="text-success" />
          ) : (
            <ArrowDown size={16} className="text-danger" />
          )}
          <span className={`font-semibold ${trend.dir === "up" ? "text-success" : "text-danger"}`}>
            {trend.text}
          </span>
        </div>
      )}
    </div>
  );
}
