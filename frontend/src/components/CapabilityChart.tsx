import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface CapabilityChartProps {
  ready: number;
  notIntegrated: number;
}

export function CapabilityChart({ ready, notIntegrated }: CapabilityChartProps) {
  const data = [
    { status: "Ready", count: ready },
    { status: "Not integrated", count: notIntegrated },
  ];

  return (
    <div className="h-64 w-full" role="img" aria-label={`${ready} engines ready, ${notIntegrated} not integrated`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#3f3f46" vertical={false} />
          <XAxis dataKey="status" stroke="#a1a1aa" tick={{ fill: "#a1a1aa", fontSize: 12 }} />
          <YAxis allowDecimals={false} stroke="#a1a1aa" tick={{ fill: "#a1a1aa", fontSize: 12 }} />
          <Tooltip
            cursor={{ fill: "#27272a" }}
            contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", color: "#fafafa" }}
          />
          <Bar dataKey="count" name="Engines" fill="#67e8f9" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
