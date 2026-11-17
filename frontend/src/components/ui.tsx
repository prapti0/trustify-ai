import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" }) {
  const tone = variant === "primary" ? "btn-primary" : "btn-secondary";
  return <button className={`btn ${tone} ${className}`} {...props} />;
}

export function TextField({
  label,
  hint,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  const id = props.id ?? props.name;
  const hintId = hint && id ? `${id}-hint` : undefined;
  return (
    <div>
      <label className="block" htmlFor={id}>
        <span className="label">{label}</span>
        <input id={id} className="field" aria-describedby={hintId} {...props} />
      </label>
      {hint ? <span id={hintId} className="mt-1 block text-xs muted">{hint}</span> : null}
    </div>
  );
}

export function TextArea({
  label,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  const id = props.id ?? props.name;
  return (
    <label className="block" htmlFor={id}>
      <span className="label">{label}</span>
      <textarea id={id} className="field min-h-32" {...props} />
    </label>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "ok" | "warn" | "danger" | "info" }) {
  const color =
    tone === "ok"
      ? "var(--ok)"
      : tone === "warn"
        ? "var(--warn)"
        : tone === "danger"
          ? "var(--danger)"
          : tone === "info"
            ? "var(--blue)"
            : "var(--muted)";
  return (
    <span className="inline-flex rounded-full px-2.5 py-1 text-xs font-medium" style={{ color, border: `1px solid ${color}` }}>
      {children}
    </span>
  );
}

export function classificationTone(value: string | null | undefined): "neutral" | "ok" | "warn" | "danger" | "info" {
  if (value === "low") return "ok";
  if (value === "medium") return "warn";
  if (value === "high" || value === "critical") return "danger";
  if (value === "inconclusive") return "info";
  return "neutral";
}

export function statusTone(value: string): "neutral" | "ok" | "warn" | "danger" | "info" {
  if (value === "completed" || value === "done") return "ok";
  if (value === "failed") return "danger";
  if (value === "unavailable" || value === "skipped") return "warn";
  if (value === "processing" || value === "queued" || value === "pending") return "info";
  return "neutral";
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="card p-8 text-center">
      <h2 className="text-lg font-medium">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm muted">{body}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function Dialog({
  title,
  body,
  confirmLabel,
  busy,
  onCancel,
  onConfirm,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 p-4" role="presentation">
      <div className="card w-full max-w-md p-5" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
        <h2 id="dialog-title" className="text-lg font-medium">
          {title}
        </h2>
        <p className="mt-2 text-sm muted">{body}</p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" type="button" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" onClick={onConfirm} disabled={busy}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
