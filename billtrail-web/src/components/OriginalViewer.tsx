export default function OriginalViewer({ url, type, name }: { url: string; type: string; name: string }) {
  return (
    <div className="card overflow-hidden">
      <div className="border-b border-line px-3 py-2 text-xs text-muted">Original: {name}</div>
      {!url ? (
        <p className="p-6 text-sm text-muted">The original file is not available in demo data.</p>
      ) : type === "application/pdf" ? (
        <iframe src={url} title="Original bill" className="h-[70vh] w-full" />
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt="Original bill" className="max-h-[70vh] w-full object-contain" />
      )}
    </div>
  );
}
