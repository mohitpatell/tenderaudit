"use client";

import { useRef, useState, DragEvent } from "react";
import { Upload, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface UploadDropzoneProps {
  accept?: Record<string, string[]>;
  onFile: (file: File) => void | Promise<void>;
  loading?: boolean;
  label?: string;
  sublabel?: string;
}

export function UploadDropzone({
  accept,
  onFile,
  loading = false,
  label = "Drop file here or click to browse",
  sublabel,
}: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onFile(file);
    e.target.value = "";
  }

  const acceptStr = accept
    ? Object.entries(accept)
        .flatMap(([, exts]) => exts)
        .join(",")
    : undefined;

  return (
    <div
      className={cn(
        "relative flex flex-col items-center justify-center gap-3 py-12 rounded-lg border-2 border-dashed cursor-pointer transition-colors",
        dragging ? "border-primary bg-primary/5" : "border-slate-300 hover:border-primary/50 hover:bg-slate-50"
      )}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !loading && inputRef.current?.click()}
    >
      {loading ? (
        <>
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
          <p className="text-sm text-slate-500">Uploading…</p>
        </>
      ) : (
        <>
          <div className={cn(
            "h-12 w-12 rounded-full flex items-center justify-center transition-colors",
            dragging ? "bg-primary/10" : "bg-slate-100"
          )}>
            <Upload className={cn("h-6 w-6 transition-colors", dragging ? "text-primary" : "text-slate-400")} />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-slate-700">{label}</p>
            {sublabel && <p className="text-xs text-slate-400 mt-1">{sublabel}</p>}
          </div>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={acceptStr}
        className="hidden"
        onChange={handleChange}
        disabled={loading}
      />
    </div>
  );
}
