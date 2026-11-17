export function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes)) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = units[0];
  for (let index = 0; index < units.length; index += 1) {
    unit = units[index];
    if (value < 1024 || index === units.length - 1) break;
    value /= 1024;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${unit}`;
}

export function formatWhen(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

const specialWords: Record<string, string> = {
  ai: "AI",
  c2pa: "C2PA",
  id: "ID",
  pdf: "PDF",
  sha256: "SHA-256",
  url: "URL",
};

export function labelize(value: string) {
  return value
    .split("_")
    .map((word) => specialWords[word] ?? `${word.slice(0, 1).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

export function classificationLabel(value: string) {
  const named: Record<string, string> = {
    low: "Low Risk",
    medium: "Medium Risk",
    high: "High Risk",
    critical: "Critical Risk",
    inconclusive: "Inconclusive",
  };
  return named[value] ?? labelize(value);
}
