import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { errorMessage, getDashboard } from "../api/client";
import type { CountPoint, DashboardData } from "../api/types";
import { AppShell } from "../components/Shell";
import { Badge, classificationTone, EmptyState, statusTone } from "../components/ui";
import { classificationLabel, formatWhen, labelize } from "../lib/format";

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboard().then(setData).catch((reason) => setError(errorMessage(reason, "Dashboard records could not be loaded.")));
  }, []);

  return (
    <AppShell title="Security & Authenticity Dashboard" subtitle="Monitor your digital content investigations and analysis activity.">
      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {!data && !error ? <p className="text-sm muted">Loading your records…</p> : null}
      {data ? <DashboardBody data={data} /> : null}
    </AppShell>
  );
}

function DashboardBody({ data }: { data: DashboardData }) {
  const cards = [
    ["Total Files Analyzed", data.total_files, "Files stored for this account."],
    ["AI-Generated Indicators", data.ai_generated_indicators, data.notes.ai_generated_indicators],
    ["Suspicious Files", data.suspicious_files, data.notes.suspicious_files],
    ["Deepfake Indicators", data.deepfake_indicators, data.notes.deepfake_indicators],
    ["Security Threats Detected", data.security_threats, data.notes.security_threats],
    ["Completed Investigations", data.completed_investigations, "Jobs that finished the available checks."],
  ] as const;
  const charts = [
    ["File Types Analyzed", data.file_types],
    ["Risk Classification Distribution", data.risk_distribution],
    ["Detection Results", data.detection_results],
    ["Analysis Activity Over Time", data.activity.map((point) => ({ label: point.date, count: point.count }))],
  ] as const;
  const hasActivity = data.total_files > 0;

  return (
    <div className="grid gap-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cards.map(([label, value, note]) => (
          <article key={label} className="card p-5">
            <p className="text-sm muted">{label}</p>
            <p className="mt-2 text-3xl font-medium">{value}</p>
            <p className="mt-2 text-xs leading-relaxed muted">{note}</p>
          </article>
        ))}
      </section>

      <section>
        <h2 className="text-lg font-medium">Recent Activity</h2>
        {data.recent.length === 0 ? (
          <div className="mt-3">
            <EmptyState title="No files analyzed yet." body="Upload a supported file to create the first investigation record." action={<Link to="/app/analyze" className="btn btn-primary">New Analysis</Link>} />
          </div>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <JobTable jobs={data.recent} />
          </div>
        )}
      </section>

      <section>
        <h2 className="text-lg font-medium">Analysis Distribution</h2>
        {hasActivity ? (
          <div className="mt-3 grid gap-4 xl:grid-cols-2">
            {charts.map(([title, points]) => (
              <ChartCard key={title} title={title} points={points} />
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm muted">Charts appear after the first completed upload. No sample statistics are shown.</p>
        )}
      </section>

      <section>
        <h2 className="text-lg font-medium">Quick Actions</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link className="btn btn-secondary" to="/app/analyze?kind=video">Analyze a Video</Link>
          <Link className="btn btn-secondary" to="/app/analyze?kind=image">Analyze an Image</Link>
          <Link className="btn btn-secondary" to="/app/analyze?kind=document">Scan a Document</Link>
          <Link className="btn btn-secondary" to="/app/analyze?kind=url">Check a Suspicious URL</Link>
        </div>
      </section>
    </div>
  );
}

export function JobTable({ jobs }: { jobs: DashboardData["recent"] }) {
  return (
    <table className="w-full min-w-[760px] text-left text-sm">
      <thead className="muted">
        <tr>
          {["File Name", "File Type", "Analysis Date", "Analysis Status", "Risk Classification", "Actions"].map((heading) => (
            <th key={heading} className="border-b border-[var(--line)] py-2 pr-3 font-medium">{heading}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {jobs.map((job) => (
          <tr key={job.job_id}>
            <td className="border-b border-[var(--line)] py-3 pr-3">{job.file_name}</td>
            <td className="border-b border-[var(--line)] py-3 pr-3">{job.file_type}</td>
            <td className="border-b border-[var(--line)] py-3 pr-3">{formatWhen(job.created_at)}</td>
            <td className="border-b border-[var(--line)] py-3 pr-3"><Badge tone={statusTone(job.status)}>{labelize(job.status)}</Badge></td>
            <td className="border-b border-[var(--line)] py-3 pr-3"><Badge tone={classificationTone(job.classification)}>{job.classification ? classificationLabel(job.classification) : "None"}</Badge></td>
            <td className="border-b border-[var(--line)] py-3">
              <Link className="text-[var(--blue)]" to={`/app/reports/${job.job_id}`}>View Report</Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ChartCard({ title, points }: { title: string; points: readonly CountPoint[] }) {
  return (
    <article className="card p-4">
      <h3 className="text-sm font-medium">{title}</h3>
      <div className="mt-3 h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={[...points]}>
            <CartesianGrid stroke="#8ea0b8" vertical={false} />
            <XAxis dataKey="label" stroke="#8ea0b8" tick={{ fill: "#8ea0b8", fontSize: 12 }} />
            <YAxis allowDecimals={false} stroke="#8ea0b8" tick={{ fill: "#8ea0b8", fontSize: 12 }} label={{ value: "Count", angle: -90, position: "insideLeft", fill: "#8ea0b8" }} />
            <Tooltip />
            <Bar dataKey="count" name="Records" fill="#2f6bff" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs muted">Source: records stored for this account.</p>
    </article>
  );
}
