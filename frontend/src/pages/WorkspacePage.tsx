import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage, getPlatform, listDuplicates, listJobs, submitScam, submitUrl } from "../api/client";
import type { DuplicateMatch, EngineCapability, JobSummary, ScamResult } from "../api/types";
import { AppShell } from "../components/Shell";
import { Badge, Button, EmptyState, TextArea } from "../components/ui";
import { labelize } from "../lib/format";
import { Preview } from "./Preview";

interface WorkspaceConfig {
  title: string;
  description: string;
  category?: string;
  engineId: string;
  features: string[];
}

const configs: Record<string, WorkspaceConfig> = {
  video: {
    title: "Advanced Video Forensics",
    description: "Investigate video authenticity, frame-level manipulation and suspicious editing patterns.",
    category: "video",
    engineId: "video_forensics",
    features: ["Video Frame Extraction", "Deepfake Detection", "Face Manipulation Analysis", "Lip-Sync Verification", "Audio-Video Synchronization", "Metadata Analysis", "Duplicate Frame Detection", "Video Similarity Matching", "Compression Analysis"],
  },
  image: {
    title: "Image Authenticity Analysis",
    description: "Investigate AI-generated images and visual manipulation.",
    category: "image",
    engineId: "image_forensics",
    features: ["AI Image Detection", "Face Manipulation Detection", "EXIF Metadata", "Image Compression Analysis", "Perceptual Hashing", "C2PA Verification", "Supported Watermark Detection"],
  },
  audio: {
    title: "Audio & Voice Forensics",
    description: "Analyze audio authenticity, synthetic speech and suspicious voice modifications.",
    category: "audio",
    engineId: "audio_forensics",
    features: ["AI Voice Detection", "Voice Cloning Indicators", "Audio Manipulation Detection", "Speech-to-Text", "Audio Spectrogram", "Background Noise Analysis", "Audio Similarity"],
  },
  documents: {
    title: "Document Forensics",
    description: "Inspect documents for suspicious content, metadata inconsistencies and file security risks.",
    category: "document",
    engineId: "document_forensics",
    features: ["Metadata Extraction", "PDF Structure Analysis", "Digital Signature Verification", "Embedded File Detection", "Suspicious Link Detection", "Script and Macro Inspection", "Document Integrity Analysis"],
  },
  security: {
    title: "File Security Scanner",
    description: "Identify potentially malicious files and suspicious embedded content.",
    engineId: "malware_scanner",
    features: ["Malware Scanning", "YARA Rule Analysis", "SHA-256 Hashing", "Archive Inspection", "Suspicious File Detection", "URL Reputation Checks"],
  },
};

export function WorkspacePage({ kind }: { kind: keyof typeof configs }) {
  const config = configs[kind];
  const [engine, setEngine] = useState<EngineCapability | null>(null);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPlatform()
      .then((platform) => setEngine(platform.engines.find((item) => item.id === config.engineId) ?? null))
      .catch((reason) => setError(errorMessage(reason, "Engine status could not be loaded.")));
    listJobs()
      .then((rows) =>
        setJobs(
          config.category
            ? rows.filter((job) =>
                config.category === "document" ? job.category === "document" || job.category === "data" : job.category === config.category,
              )
            : rows,
        ),
      )
      .catch((reason) => setError(errorMessage(reason, "Files could not be loaded.")));
  }, [config.category, config.engineId]);

  const current = jobs.find((job) => job.job_id === selected) ?? null;

  return (
    <AppShell title={config.title} subtitle={config.description}>
      {error ? <p className="mb-4 text-sm text-[var(--danger)]">{error}</p> : null}
      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <div className="grid gap-4">
          {engine ? (
            <section className="card p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-medium">Engine status</h2>
                <Badge tone={engine.status === "ready" ? "ok" : "warn"}>{labelize(engine.status)}</Badge>
              </div>
              <p className="mt-2 text-sm muted">{engine.detail}</p>
              {kind === "security" ? (
                <p className="mt-2 text-sm">Possible recorded results are Clean, Suspicious, Malicious, Scan Failed, or Inconclusive. A scanner that did not run is not shown as Clean.</p>
              ) : null}
            </section>
          ) : null}
          {jobs.length === 0 ? (
            <EmptyState title="No files analyzed yet." body="Upload a supported file to see it in this workspace." action={<Link className="btn btn-primary" to="/app/analyze">New Analysis</Link>} />
          ) : (
            <ul className="card divide-y divide-[var(--line)]">
              {jobs.map((job) => (
                <li key={job.job_id}>
                  <button type="button" className="flex w-full items-center justify-between px-4 py-3 text-left text-sm" onClick={() => setSelected(job.job_id)}>
                    <span>{job.file_name}</span>
                    <span className="muted">{job.classification ?? job.status}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {current ? (
            <section className="report-sheet p-5">
              <h2 className="font-medium">{current.file_name}</h2>
              <Preview fileId={current.file_id} category={current.category} name={current.file_name} />
              <Link className="mt-4 inline-block text-sm text-[#1d4ed8]" to={`/app/reports/${current.job_id}`}>Open the full report</Link>
            </section>
          ) : null}
        </div>
        <aside className="card h-fit p-5">
          <h2 className="font-medium">Included checks</h2>
          <ul className="mt-3 space-y-2 text-sm muted">
            {config.features.map((feature) => <li key={feature}>{feature}</li>)}
          </ul>
        </aside>
      </div>
    </AppShell>
  );
}

export function DuplicatesPage() {
  const [rows, setRows] = useState<DuplicateMatch[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    listDuplicates().then(setRows).catch((reason) => setError(errorMessage(reason, "Duplicate records could not be loaded.")));
  }, []);
  return (
    <AppShell title="Duplicate & Similarity Investigation" subtitle="Identify identical and similar content across your authorized reference library.">
      <p className="mb-4 max-w-3xl text-sm muted">This page searches files uploaded to your account. It does not search the public internet. Perceptual image, video-frame, and audio fingerprint matching are not integrated.</p>
      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {rows && rows.length === 0 ? <EmptyState title="No duplicate matches found." body="Exact SHA-256 matches appear here after the same bytes are uploaded more than once." /> : null}
      {rows && rows.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] text-left text-sm">
            <thead className="muted">
              <tr>{["Original File", "Matched File", "Similarity", "Matching Method"].map((heading) => <th key={heading} className="border-b border-[var(--line)] py-2 pr-3 font-medium">{heading}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.file_id}-${row.matched_file_id}`}>
                  <td className="border-b border-[var(--line)] py-3 pr-3">{row.file_name}</td>
                  <td className="border-b border-[var(--line)] py-3 pr-3">{row.matched_file_name}</td>
                  <td className="border-b border-[var(--line)] py-3 pr-3">{row.match_kind === "exact_hash" ? "Exact" : row.distance ?? "Not scored"}</td>
                  <td className="border-b border-[var(--line)] py-3">{labelize(row.match_kind)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </AppShell>
  );
}

export function ScamPage() {
  const navigate = useNavigate();
  const [kind, setKind] = useState<"media" | "url" | "message" | "claim">("message");
  const [content, setContent] = useState("");
  const [result, setResult] = useState<ScamResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (kind === "url") {
        const report = await submitUrl(content.trim());
        navigate(`/app/reports/${report.job_id}`);
        return;
      }
      setResult(await submitScam(kind, content));
    } catch (reason) {
      setError(errorMessage(reason, "The investigation could not be submitted."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell title="AI Scam Investigation" subtitle="Investigate suspicious media, links and digital claims using multiple evidence sources.">
      <form onSubmit={onSubmit} className="card grid max-w-3xl gap-4 p-5">
        <label className="label" htmlFor="scam-kind">Input</label>
        <select id="scam-kind" className="field" value={kind} onChange={(event) => setKind(event.target.value as typeof kind)}>
          <option value="media">Upload Suspicious Media</option>
          <option value="url">Submit a Website URL</option>
          <option value="message">Submit a Suspicious Message</option>
          <option value="claim">Submit a Claim for Verification</option>
        </select>
        {kind === "media" ? <p className="text-sm muted">Use New Analysis to upload the file. Paste the context of the media here. The file itself is not fetched from this form.</p> : null}
        {kind === "url" ? <p className="text-sm muted">Website URLs are checked with URL reputation. Video platform URLs use public metadata only. Instagram/Facebook media links are not fetched.</p> : null}
        <TextArea label="Submission" name="content" required value={content} onChange={(event) => setContent(event.target.value)} />
        {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
        <Button type="submit" disabled={busy}>Review submission</Button>
      </form>
      {result ? (
        <section className="report-sheet mt-6 max-w-3xl p-5">
          <Badge tone="warn">{labelize(result.status)}</Badge>
          <h2 className="mt-3 text-lg font-medium">Investigation Summary</h2>
          <p className="mt-2 text-sm">{result.summary}</p>
          <h3 className="mt-4 font-medium">Unverified input</h3>
          <p className="mt-1 text-sm">{result.unverified_input}</p>
          <h3 className="mt-4 font-medium">Evidence Collected</h3>
          <p className="mt-1 text-sm muted">{result.evidence.length === 0 ? "No evidence was collected." : result.evidence.join(" ")}</p>
          <h3 className="mt-4 font-medium">Risk Indicators</h3>
          <p className="mt-1 text-sm muted">{result.risk_indicators.length === 0 ? "No risk indicator was produced." : result.risk_indicators.join(" ")}</p>
          <h3 className="mt-4 font-medium">Recommended Actions</h3>
          <ul className="mt-1 list-disc pl-5 text-sm">{result.recommended_steps.map((step) => <li key={step}>{step}</li>)}</ul>
        </section>
      ) : null}
    </AppShell>
  );
}
