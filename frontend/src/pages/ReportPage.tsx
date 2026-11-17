import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { downloadReportPdf, errorMessage, getJob } from "../api/client";
import type { Report } from "../api/types";
import { AppShell } from "../components/Shell";
import { Badge, classificationTone, statusTone } from "../components/ui";
import { useToast } from "../context/ToastContext";
import { classificationLabel, formatBytes, formatWhen, labelize } from "../lib/format";
import { Preview } from "./Preview";

const moduleTitles: Record<string, string> = {
  file_signature: "File Integrity",
  sha256: "File Integrity",
  container_metadata: "Metadata Analysis",
  url_oembed: "Public URL Metadata",
  youtube_oembed: "Public URL Metadata",
  url_reputation: "URL Reputation / Phishing Check",
  image_forensics: "Deepfake Analysis",
  video_forensics: "Video Frame Forensics",
  ai_content_detection: "AI Image Detection",
  audio_forensics: "Audio Analysis",
  document_forensics: "Document Forensics",
  malware_scanner: "Security Analysis",
  duplicate_perceptual: "Similarity Analysis",
  provenance: "Provenance Analysis",
  scam_investigation: "Scam Investigation",
  fusion: "Evidence Correlation",
};

export function ReportPage() {
  const { jobId = "" } = useParams();
  const { push } = useToast();
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [technical, setTechnical] = useState(false);

  useEffect(() => {
    let active = true;
    const load = () => {
      getJob(jobId)
        .then((next) => {
          if (active) setReport(next);
        })
        .catch((reason) => {
          if (active) setError(errorMessage(reason, "The report could not be loaded."));
        });
    };
    load();
    const timer = window.setInterval(() => {
      if (!active) return;
      setReport((current) => {
        if (current && (current.status === "queued" || current.status === "processing")) {
          load();
        }
        return current;
      });
    }, 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [jobId]);

  return (
    <AppShell title="Digital Forensics Report" subtitle="Detailed analysis and evidence collected from your uploaded content.">
      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {!report && !error ? <p className="muted">Loading the report…</p> : null}
      {report ? (
        <article className="report-sheet p-6 md:p-8">
          <header className="grid gap-2 text-sm md:grid-cols-2">
            <p>File Name: {report.file_name}</p>
            <p>File Type: {report.file_type}</p>
            <p>File Size: {formatBytes(report.size_bytes)}</p>
            <p className="break-all">SHA-256 Hash: {report.sha256}</p>
            <p>Analysis Date: {formatWhen(report.created_at)}</p>
            <p className="break-all">Report ID: {report.job_id}</p>
          </header>
          <section className="mt-8">
            <h2 className="text-xl font-medium">Overall Assessment</h2>
            <div className="mt-3">
              <Badge tone={classificationTone(report.classification)}>{report.classification ? classificationLabel(report.classification) : "None"}</Badge>
            </div>
            <p className="mt-3 text-sm muted">A numeric risk score is omitted because no validated scoring method is implemented.</p>
            {report.classification === "inconclusive" ? (
              <p className="mt-3 max-w-3xl rounded-xl border border-[#e1e6ef] bg-white p-3 text-sm">
                <span className="font-medium">Inconclusive is expected right now.</span> Upload and integrity checks can succeed while AI/deepfake detectors stay unavailable. That is not a verdict that the media is real or fake.
              </p>
            ) : null}
            <p className="mt-3 max-w-3xl text-sm">{report.summary}</p>
          </section>
          {report.metadata ? (
            <section className="mt-8">
              <h2 className="text-xl font-medium">Metadata Analysis</h2>
              <p className="mt-2 text-sm muted">Recorded container fields only. Missing metadata is not proof of synthetic content.</p>
              <dl className="mt-4 grid gap-3 text-sm md:grid-cols-2">
                <div><dt className="muted">Container</dt><dd>{report.metadata.container ?? "Not recorded"}</dd></div>
                <div><dt className="muted">Codec / brand</dt><dd>{report.metadata.codec ?? "Not recorded"}</dd></div>
                <div><dt className="muted">Dimensions</dt><dd>{report.metadata.width && report.metadata.height ? `${report.metadata.width}×${report.metadata.height}` : "Not recorded"}</dd></div>
                <div><dt className="muted">Duration</dt><dd>{report.metadata.duration_seconds != null ? `${report.metadata.duration_seconds}s` : "Not recorded"}</dd></div>
              </dl>
              {report.metadata.extra && Object.keys(report.metadata.extra).length > 0 ? (
                <pre className="mt-4 overflow-x-auto rounded-xl border border-[#e1e6ef] bg-white p-3 text-xs">{JSON.stringify(report.metadata.extra, null, 2)}</pre>
              ) : null}
            </section>
          ) : null}
          <Preview fileId={report.file_id} category={report.category} name={report.file_name} />
          <section className="mt-8 grid gap-4">
            <h2 className="text-xl font-medium">Analysis Modules</h2>
            {report.modules.map((module) => (
              <section key={module.module} className="rounded-xl border border-[#e1e6ef] p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-medium">{moduleTitles[module.module] ?? labelize(module.module)}</h3>
                  <Badge tone={statusTone(module.status)}>{labelize(module.status)}</Badge>
                </div>
                <p className="mt-2 text-sm">Finding: {module.finding_label ? labelize(module.finding_label) : "None recorded"}</p>
                <p className="mt-1 text-sm">Confidence level: {module.confidence === null ? "Not produced" : module.confidence}</p>
                <p className="mt-2 text-sm muted">{module.limitations}</p>
              </section>
            ))}
          </section>
          <section className="mt-8">
            <h2 className="text-xl font-medium">Investigation Findings</h2>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <Finding title="Key Findings" items={report.summary ? [report.summary] : []} />
              <Finding title="Evidence" items={report.evidence.map((item) => `${item.severity}: ${item.observation}`)} />
              <Finding title="Warnings" items={report.warnings} />
              <Finding title="Unverified Claims" items={report.unverified_claims} empty="No unverified claim was submitted with this file." />
              <Finding title="Recommended Next Steps" items={report.recommended_steps} />
            </div>
            <p className="mt-4 text-sm muted">{report.limitations}</p>
          </section>
          <div className="mt-6 flex flex-wrap gap-2">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                void downloadReportPdf(report.job_id).catch((reason) => push(errorMessage(reason, "PDF report export is not implemented."), "danger"));
              }}
            >
              Download PDF Report
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setTechnical((value) => !value)}>
              View Technical Details
            </button>
            <Link to="/app/analyze" className="btn btn-secondary">Start New Analysis</Link>
          </div>
          {technical ? (
            <pre className="mt-4 overflow-x-auto rounded-xl bg-[#101828] p-4 text-xs text-[#e8eef8]">{JSON.stringify(report.sections, null, 2)}</pre>
          ) : null}
        </article>
      ) : null}
    </AppShell>
  );
}

function Finding({ title, items, empty = "None recorded." }: { title: string; items: string[]; empty?: string }) {
  return (
    <section>
      <h3 className="font-medium">{title}</h3>
      {items.length === 0 ? <p className="mt-2 text-sm muted">{empty}</p> : (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
          {items.map((item) => <li key={item}>{item}</li>)}
        </ul>
      )}
    </section>
  );
}
