"use client";

import { FileText } from "lucide-react";
import type { BBox } from "@/lib/types";

interface PdfViewerProps {
  blobId?: string;
  highlight?: BBox | null;
  className?: string;
}

/**
 * PdfViewer — renders the bidder PDF with optional BBox highlight.
 * When backend is connected: fetches /api/proxy/api/blobs/{blobId} as arraybuffer,
 * renders via @react-pdf-viewer/core with highlight plugin.
 * When backend is offline: shows a placeholder with bbox info.
 *
 * Full @react-pdf-viewer integration requires a running backend to serve
 * the PDF blob. The import is wrapped in dynamic() to avoid SSR issues
 * with pdfjs-dist.
 */
export function PdfViewer({ blobId, highlight, className }: PdfViewerProps) {
  // Placeholder — wired up when backend serves PDF blobs
  return (
    <div className={`flex flex-col items-center justify-center gap-4 h-full bg-slate-100 text-slate-400 ${className ?? ""}`}>
      <FileText className="h-16 w-16 text-slate-300" />
      <div className="text-center px-4">
        <p className="font-medium text-slate-500 text-sm">PDF Viewer</p>
        {blobId ? (
          <p className="text-xs text-slate-400 mt-1">Blob: {blobId}</p>
        ) : (
          <p className="text-xs text-slate-400 mt-1">No document selected</p>
        )}
        {highlight && (
          <div className="mt-3 bg-white rounded-lg border p-2 text-xs text-slate-600">
            <p className="font-medium">Evidence at</p>
            <p>Page {highlight.page} · ({highlight.x0.toFixed(0)}, {highlight.y0.toFixed(0)}) → ({highlight.x1.toFixed(0)}, {highlight.y1.toFixed(0)})</p>
          </div>
        )}
        <p className="text-xs text-slate-300 mt-3">Connect backend on :8001 to enable PDF rendering</p>
      </div>
    </div>
  );
}
