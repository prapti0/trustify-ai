import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { errorMessage, getJob } from "../api/client";
import type { Report } from "../api/types";
import { AppShell } from "../components/Shell";
import { Badge, statusTone } from "../components/ui";
import { labelize } from "../lib/format";

export function ProcessingPage() {
  const { jobId = "" } = useParams();
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = () => {
      getJob(jobId)
        .then((next) => {
          if (active) setReport(next);
        })
        .catch((reason) => {
          if (active) setError(errorMessage(reason, "Analysis failed. Please try again."));
        });
    };
    load();
    const timer = window.setInterval(load, 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [jobId]);

  const current =
    report?.stages.find((stage) => stage.state === "processing" || stage.state === "pending") ??
    (report?.status === "completed" || report?.status === "failed" ? undefined : report?.stages.at(-1));

  return (
    <AppShell title="Analyzing Your Content" subtitle="Our investigation engine is examining your file.">
      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {!report && !error ? <p className="text-sm muted">Loading the analysis job…</p> : null}
      {report ? (
        <div className="grid gap-5">
          <div className="card p-5 text-sm">
            <p>Analysis Job ID <span className="font-mono">{report.job_id}</span></p>
            <p className="mt-2">Processing Status <Badge tone={statusTone(report.status)}>{labelize(report.status)}</Badge></p>
            <p className="mt-2">Current Processing Stage: {current?.label ?? (report.status === "completed" ? "Report ready" : "Waiting")}</p>
            <p className="mt-2 muted">Estimated time is hidden because this build does not have a reliable duration model.</p>
            {report.status === "completed" ? (
              <Link className="btn btn-primary mt-4" to={`/app/reports/${report.job_id}`}>Open report</Link>
            ) : null}
            {report.status === "failed" ? (
              <p className="mt-4 text-sm text-[var(--danger)]">Analysis failed. Please try again. Incomplete stages are not clean findings.</p>
            ) : null}
          </div>
          <ol className="grid gap-3">
            {report.stages.map((stage, index) => (
              <li key={stage.id} className="card p-4">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="font-medium">{index + 1}. {stage.label}</h2>
                  <Badge tone={statusTone(stage.state)}>{labelize(stage.state)}</Badge>
                </div>
                <p className="mt-2 text-sm muted">{stage.detail}</p>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </AppShell>
  );
}
