import { Link } from "react-router-dom";
import { MarketingFooter, MarketingHeader } from "../components/Marketing";

const features = [
  ["AI Content Detection", "Identify AI-generated images, videos, audio and synthetic content when a model is actually registered."],
  ["Deepfake Detection", "A place for facial manipulation, face swapping, and lip-sync checks. Those models are not running in this build."],
  ["Video Forensics", "Reserved for frames, metadata, compression, and editing inconsistencies."],
  ["Audio Forensics", "Reserved for synthetic voices, cloning indicators, and audio manipulation."],
  ["File Security", "Hash and signature checks run today. Malware scanners are reported as not invoked."],
  ["Duplicate Detection", "Exact SHA-256 matches are compared inside your own uploads. This is not an internet search."],
  ["Content Provenance", "C2PA, signatures, and watermarks stay unavailable until a verifier is connected. Missing metadata is not proof of a fake."],
  ["Scam Investigation", "Submissions are stored as unverified input. The product will not label a person or business a scammer without evidence."],
];

const steps = [
  ["01", "Upload or Submit", "Upload a supported file. Public URL fetching is not enabled, and the form says so."],
  ["02", "AI Analysis", "Each engine reports done, or unavailable. An unavailable engine does not invent a score."],
  ["03", "Evidence Correlation", "Hash, signature, and exact duplicates are recorded separately. They are not averaged."],
  ["04", "Get Your Report", "You receive an inconclusive classification until the missing detectors produce real findings."],
];

export function LandingPage() {
  return (
    <div>
      <MarketingHeader />
      <main>
        <section className="mx-auto grid max-w-6xl items-end gap-10 px-5 py-16 md:grid-cols-[1.3fr_0.7fr]">
          <div>
            <p className="text-sm font-medium text-[var(--violet)]">Digital forensics platform</p>
            <h1 className="mt-3 max-w-3xl text-5xl font-medium leading-tight">Verify What's Real. Detect What's Fake.</h1>
            <p className="mt-4 max-w-2xl text-lg muted">
              Your all-in-one AI-powered digital forensics platform. Analyze videos, images, audio and documents to uncover
              AI-generated content, deepfakes, manipulation, suspicious files and digital threats.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/register" className="btn btn-primary">
                Start Free Analysis
              </Link>
              <a href="#features" className="btn btn-secondary">
                Explore Features
              </a>
            </div>
          </div>
          <ul className="card divide-y divide-[var(--line)]">
            {["Multimodal AI Analysis", "Digital Forensics", "Secure File Processing", "Evidence-Based Reports"].map((item) => (
              <li key={item} className="px-5 py-4 text-sm">
                {item}
              </li>
            ))}
          </ul>
        </section>

        <section id="features" className="mx-auto max-w-6xl px-5 py-8">
          <h2 className="text-3xl font-medium">Everything You Need to Verify Digital Content</h2>
          <p className="mt-3 max-w-3xl muted">Advanced detection and forensic tools working together in one intelligent platform.</p>
          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {features.map(([title, body]) => (
              <article key={title} className="card p-5">
                <h3 className="font-medium">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed muted">{body}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="how-it-works" className="mx-auto max-w-6xl px-5 py-12">
          <h2 className="text-3xl font-medium">How It Works</h2>
          <ol className="mt-8 grid gap-4 md:grid-cols-4">
            {steps.map(([number, title, body]) => (
              <li key={number} className="card p-5">
                <p className="font-mono text-xs text-[var(--blue)]">{number}</p>
                <h3 className="mt-3 font-medium">{title}</h3>
                <p className="mt-2 text-sm muted">{body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="technology" className="mx-auto max-w-6xl px-5 py-8">
          <h2 className="text-3xl font-medium">Technology</h2>
          <p className="mt-3 max-w-3xl muted">
            The API, account system, object storage, and SHA-256 checks are running. Image, video, audio, document, malware,
            provenance, and Gemini investigation engines are listed as not integrated on the documentation page. Installing a
            library does not turn those engines on.
          </p>
        </section>

        <section className="mx-auto max-w-6xl px-5 py-16">
          <div className="card flex flex-wrap items-center justify-between gap-6 p-8">
            <div>
              <h2 className="text-3xl font-medium">Don't Trust Every File. Verify It.</h2>
              <p className="mt-2 muted">Analyze digital content with intelligent forensic tools.</p>
            </div>
            <Link to="/register" className="btn btn-primary">
              Analyze Your First File
            </Link>
          </div>
        </section>
      </main>
      <MarketingFooter />
    </div>
  );
}
