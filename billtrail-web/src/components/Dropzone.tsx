"use client";
import { useRef, useState } from "react";

const MAX_MB = 15;

export default function Dropzone({ onFile, error }: { onFile: (f: File) => void; error?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [localError, setLocalError] = useState("");

  function pick(f?: File) {
    if (!f) return;
    if (!/^image\/|^application\/pdf$/.test(f.type)) return setLocalError("Choose a PDF or a photo (JPG, PNG).");
    if (f.size > MAX_MB * 1048576) return setLocalError(`File is larger than ${MAX_MB} MB.`);
    setLocalError(""); onFile(f);
  }

  return (
    <div>
      <button type="button" onClick={() => input.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]); }}
        className={`flex w-full flex-col items-center gap-1 rounded-lg border-2 border-dashed px-6 py-16 text-center transition-colors ${over ? "border-accent bg-accent/5" : "border-line bg-panel hover:border-accent"}`}>
        <span className="text-base font-medium">Drop a bill here, or choose a file</span>
        <span className="text-sm text-muted">PDF or phone photo, up to {MAX_MB} MB</span>
      </button>
      <input ref={input} type="file" accept="image/*,application/pdf" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
      {(localError || error) && <p role="alert" className="mt-3 text-sm text-bad">{localError || error}</p>}
    </div>
  );
}
