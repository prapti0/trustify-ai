import { useEffect, useState } from "react";
import { getFileBlob } from "../api/client";

export function Preview({ fileId, category, name }: { fileId: string; category: string; name: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const visual = category === "image" || category === "video" || category === "audio" || category === "document";

  useEffect(() => {
    if (!visual && category !== "data") return;
    let objectUrl = "";
    let active = true;
    getFileBlob(fileId)
      .then(async (blob) => {
        if (!active) return;
        if (category === "data" || name.endsWith(".txt")) {
          setText(await blob.text());
          return;
        }
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (active) setError("Preview could not be loaded.");
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [fileId, category, name, visual]);

  if (category === "archive") {
    return <p className="mt-6 text-sm muted">Archive preview is unavailable. The package was not unpacked or executed.</p>;
  }
  if (error) return <p className="mt-6 text-sm">{error}</p>;
  if (text) return <pre className="mt-6 max-h-80 overflow-auto rounded-xl bg-white p-4 text-xs">{text}</pre>;
  if (!url) return null;
  if (category === "image") return <img className="mt-6 max-h-96 rounded-xl" src={url} alt={name} />;
  if (category === "video") return <video className="mt-6 max-h-96 w-full rounded-xl" controls src={url} />;
  if (category === "audio") return <audio className="mt-6 w-full" controls src={url} />;
  if (category === "document" && name.toLowerCase().endsWith(".pdf")) {
    return <iframe className="mt-6 h-96 w-full rounded-xl border border-[#e1e6ef]" title={name} src={url} />;
  }
  return <p className="mt-6 text-sm muted">A visual preview is not available for this format. The bytes were not executed.</p>;
}
