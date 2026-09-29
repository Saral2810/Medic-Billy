"use client";
import { useEffect, useState } from "react";
import { authHeader } from "@/lib/auth";

// Files from the API need the sign-in token, which <img> and <iframe> cannot send, so fetch them as a blob first.
export default function OriginalViewer({ url, type, name }: { url: string; type: string; name: string }) {
  const [src, setSrc] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
    if (!url) { setSrc(""); return; }
    if (url.startsWith("blob:")) { setSrc(url); return; }
    let objectUrl = ""; let cancelled = false;
    fetch(url, { headers: authHeader() })
      .then((r) => { if (!r.ok) throw new Error(); return r.blob(); })
      .then((b) => { if (!cancelled) { objectUrl = URL.createObjectURL(b); setSrc(objectUrl); } })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [url]);

  return (
    <div className="card overflow-hidden">
      <div className="border-b border-line px-3 py-2 text-xs text-muted">Original: {name}</div>
      {failed ? <p className="p-6 text-sm text-bad">The original could not be loaded.</p>
        : !src ? <p className="p-6 text-sm text-muted">{url ? "Loading original…" : "The original file is not available in demo data."}</p>
        : type === "application/pdf" ? <iframe src={src} title="Original bill" className="h-[70vh] w-full" />
        // eslint-disable-next-line @next/next/no-img-element
        : <img src={src} alt="Original bill" className="max-h-[70vh] w-full object-contain" />}
    </div>
  );
}
