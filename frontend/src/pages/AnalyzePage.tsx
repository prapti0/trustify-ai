import { useMemo, useState, type DragEvent, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { errorMessage, submitUrl, uploadFile } from "../api/client";
import { AppShell } from "../components/Shell";
import { Button } from "../components/ui";
import { useToast } from "../context/ToastContext";
import { formatBytes } from "../lib/format";

const formats = [
  ["Video", "MP4, MOV, AVI, MKV, WebM"],
  ["Images", "JPG, PNG, JPEG, WEBP, GIF"],
  ["Audio", "MP3, WAV, AAC, FLAC"],
  ["Documents", "PDF, DOCX, DOC, TXT"],
  ["Data", "CSV, XLSX, JSON, XML"],
  ["Archives", "ZIP, 7Z, TAR, GZ"],
];

export function AnalyzePage() {
  const [params] = useSearchParams();
  const kind = params.get("kind");
  const navigate = useNavigate();
  const { push } = useToast();
  const [files, setFiles] = useState<File[]>([]);
  const [progress, setProgress] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [url, setUrl] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  function addFiles(list: FileList | null) {
    if (!list) return;
    setFiles((current) => [...current, ...Array.from(list)]);
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    addFiles(event.dataTransfer.files);
  }

  async function start() {
    if (files.length === 0) {
      setMessage("Choose a file before starting analysis.");
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      let lastId = "";
      for (const file of files) {
        setProgress(0);
        const report = await uploadFile(file, setProgress);
        lastId = report.job_id;
      }
      push("File uploaded successfully.");
      navigate(`/app/jobs/${lastId}`);
    } catch (error) {
      setMessage(errorMessage(error, "Analysis failed. Please try again."));
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }

  async function onUrl(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const report = await submitUrl(url);
      push("URL analysis completed successfully.");
      navigate(`/app/jobs/${report.job_id}`);
    } catch (error) {
      setMessage(errorMessage(error, "Unable to access the submitted URL."));
    } finally {
      setBusy(false);
    }
  }

  const hint = useMemo(() => {
    if (kind === "video") return "Opened from video analysis. Any supported file can still be uploaded.";
    if (kind === "image") return "Opened from image analysis. Any supported file can still be uploaded.";
    if (kind === "document") return "Opened from document analysis. Any supported file can still be uploaded.";
    if (kind === "url") {
      return "Video links: YouTube, Vimeo, Dailymotion, TikTok, Reddit. Other http(s) links run URL reputation (Safe Browsing/VirusTotal when configured, or Google published test vectors). Instagram/Facebook media URLs are not fetched.";
    }
    return null;
  }, [kind]);

  return (
    <AppShell title="Analyze Your Digital Content" subtitle="Upload any supported file to investigate its authenticity, integrity and potential security risks.">
      {hint ? <p className="mb-4 text-sm muted">{hint}</p> : null}
      <div
        className="card border-dashed p-8 text-center"
        onDragOver={(event) => event.preventDefault()}
        onDrop={onDrop}
      >
        <h2 className="text-xl font-medium">Drag & Drop Your Files Here</h2>
        <p className="mt-2 text-sm muted">Or browse files from your device.</p>
        <label className="btn btn-secondary mt-5 cursor-pointer">
          Browse Files
          <input className="sr-only" type="file" multiple onChange={(event) => addFiles(event.target.files)} />
        </label>
      </div>
      <ul className="mt-4 grid gap-2 text-sm md:grid-cols-2">
        {formats.map(([group, list]) => (
          <li key={group} className="card px-4 py-3">
            <span className="font-medium">{group}: </span>
            <span className="muted">{list}</span>
          </li>
        ))}
      </ul>
      {files.length > 0 ? (
        <ul className="mt-4 divide-y divide-[var(--line)] card">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
              <span className="font-medium">{file.name}</span>
              <span className="muted">{formatBytes(file.size)}</span>
              <span className="muted">{file.type || "type pending server check"}</span>
              <button type="button" className="ml-auto text-[var(--blue)]" onClick={() => setFiles((current) => current.filter((_, item) => item !== index))}>
                Remove File
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {progress !== null ? (
        <div className="mt-4">
          <p className="text-sm muted">Upload progress {Math.round(progress * 100)}%</p>
          <div className="mt-2 h-2 overflow-hidden rounded bg-[var(--line)]" aria-hidden="true">
            <div className="h-full bg-[var(--blue)]" style={{ width: `${Math.round(progress * 100)}%` }} />
          </div>
        </div>
      ) : null}
      {message ? <p className="mt-4 text-sm text-[var(--danger)]">{message}</p> : null}
      <Button className="mt-4" type="button" onClick={() => void start()} disabled={busy}>
        Start Analysis
      </Button>
      <p className="mt-4 max-w-3xl text-sm muted">
        Your uploaded content will be processed securely. Analysis results depend on supported detection models and available forensic evidence.
      </p>
      <form onSubmit={onUrl} className="card mt-8 grid gap-3 p-5">
        <h2 className="text-lg font-medium">Analyze Using URL</h2>
        <p className="text-sm muted">
          Video platforms use public oEmbed + thumbnail only (no DRM bypass). Other links are checked for URL reputation. Example phishing test URL from Google: https://testsafebrowsing.appspot.com/s/phishing.html. Instagram/Facebook media URLs still require manual download + upload.
        </p>
        <label className="label" htmlFor="media-url">Public URL</label>
        <input id="media-url" className="field" placeholder="Paste a video URL or a website URL to check." value={url} onChange={(event) => setUrl(event.target.value)} />
        <Button type="submit" variant="secondary" disabled={busy}>Analyze URL</Button>
      </form>
    </AppShell>
  );
}
