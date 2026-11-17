import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getPlatform } from "../api/client";
import type { PlatformStatus } from "../api/types";
import { CapabilityChart } from "../components/CapabilityChart";
import { MarketingFrame } from "../components/Marketing";
import { countEngines } from "../lib/capabilities";

export function AboutPage() {
  return (
    <MarketingFrame>
      <h1 className="text-4xl font-medium">About TRUSTIFY AI</h1>
      <p className="mt-4 max-w-3xl text-lg muted">
        TRUSTIFY AI is an AI-powered digital forensics platform that analyzes videos, images, audio and documents to detect
        synthetic media, manipulation, suspicious files and authenticity indicators. A result is shown only when a check
        actually ran.
      </p>
    </MarketingFrame>
  );
}

export function DocumentationPage() {
  const [platform, setPlatform] = useState<PlatformStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getPlatform().then(setPlatform).catch(() => setError("The platform API is unreachable. No capability data is substituted."));
  }, []);
  const counts = platform ? countEngines(platform.engines) : null;
  return (
    <MarketingFrame>
      <h1 className="text-4xl font-medium">Documentation</h1>
      <p className="mt-4 max-w-3xl muted">API reference is served by the running API at <a className="text-[var(--blue)]" href="http://127.0.0.1:8000/docs">/docs</a>. The catalog below is the live engine list.</p>
      {error ? <p className="mt-4 text-sm text-[var(--warn)]">{error}</p> : null}
      {platform && counts ? (
        <div className="mt-8 grid gap-6">
          <div className="card p-4">
            <h2 className="font-medium">Engines by integration state</h2>
            <p className="text-sm muted">{counts.ready} ready, {counts.notIntegrated} not integrated. This is not detection accuracy.</p>
            <CapabilityChart ready={counts.ready} notIntegrated={counts.notIntegrated} />
          </div>
          <ul className="grid gap-3">
            {platform.engines.map((engine) => (
              <li key={engine.id} className="card p-4">
                <p className="font-medium">{engine.name}</p>
                <p className="text-sm muted">{engine.status}. {engine.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </MarketingFrame>
  );
}

export function PrivacyPage() {
  return (
    <MarketingFrame>
      <h1 className="text-4xl font-medium">Privacy Policy</h1>
      <div className="mt-4 max-w-3xl space-y-3 text-sm leading-relaxed muted">
        <p>Account email, password hash, sessions, and uploaded bytes are stored for the signed-in user. Files are not shared with other accounts.</p>
        <p>Local development stores bytes on the API machine. S3 is not connected. There is no automatic deletion schedule.</p>
        <p>You can delete uploads or the whole account from Settings. Password hashes are not reversible. Uploaded files are not executed.</p>
      </div>
    </MarketingFrame>
  );
}

export function TermsPage() {
  return (
    <MarketingFrame>
      <h1 className="text-4xl font-medium">Terms of Service</h1>
      <div className="mt-4 max-w-3xl space-y-3 text-sm leading-relaxed muted">
        <p>Use TRUSTIFY AI only for files and URLs you are allowed to inspect. The service does not bypass logins, DRM, or encryption.</p>
        <p>Reports describe the checks that ran. An inconclusive result is not a certificate of authenticity, and an unavailable scanner is not a clean bill of health.</p>
        <p>Detection models can be wrong when they are later enabled. Do not treat a model confidence value as legal proof.</p>
      </div>
    </MarketingFrame>
  );
}

export function ContactPage() {
  return (
    <MarketingFrame>
      <h1 className="text-4xl font-medium">Contact</h1>
      <p className="mt-4 max-w-3xl muted">A contact inbox is not connected, so this page does not pretend to send a message. Use the project repository for issues, and the in-app Help page for product limits.</p>
      <Link className="btn btn-secondary mt-6" to="/app/help">Help & Support</Link>
    </MarketingFrame>
  );
}

export function HelpPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <h2 className="text-2xl font-medium">Help & Support</h2>
      <ul className="mt-4 space-y-3 text-sm muted">
        <li>Unsupported file format. The server rejects types outside the published list, and files whose bytes do not match the extension.</li>
        <li>File size exceeds the configured limit. The current limit is shown on the documentation catalog.</li>
        <li>Unable to access the submitted URL. Public fetching is disabled, so the URL is not downloaded.</li>
        <li>Detection model is currently unavailable. The report says unavailable instead of showing a score.</li>
        <li>No duplicate matches found means the hash was not seen before in your account. It does not mean the file is unique on the internet.</li>
      </ul>
    </div>
  );
}
