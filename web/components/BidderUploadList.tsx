"use client";

import { FileArchive, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface BidderEntry {
  id: string;
  name: string;
  file: File;
}

interface BidderUploadListProps {
  bidders: BidderEntry[];
  onRemove: (id: string) => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function BidderUploadList({ bidders, onRemove }: BidderUploadListProps) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-slate-700 mb-3">Bidder Documents</p>
      {bidders.map((b) => (
        <Card key={b.id} className="border-slate-200">
          <CardContent className="p-3 flex items-center gap-3">
            <div className="h-9 w-9 rounded bg-slate-100 flex items-center justify-center flex-shrink-0">
              <FileArchive className="h-4 w-4 text-slate-500" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-slate-800 truncate capitalize">{b.name}</p>
              <p className="text-xs text-slate-400">{b.file.name} · {formatBytes(b.file.size)}</p>
            </div>
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 flex-shrink-0 text-slate-400 hover:text-rose-500"
              onClick={() => onRemove(b.id)}
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
