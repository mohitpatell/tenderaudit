"use client";

import { useState, type DragEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import { Upload, ArrowRight, FileArchive } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { BidderUploadList } from "@/components/BidderUploadList";
import { evaluateTender, uploadBidder } from "@/lib/api";

interface BidderEntry {
  id: string;
  name: string;
  file: File;
}

type Stage = "idle" | "uploading" | "evaluating";

function isZipFile(file: File): boolean {
  if (file.name.toLowerCase().endsWith(".zip")) return true;
  return file.type === "application/zip" || file.type === "application/x-zip-compressed";
}

function deriveBidderName(filename: string): string {
  return filename
    .replace(/\.(zip|pdf)$/i, "")
    .replace(/^bidder-/i, "")
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function UploadBiddersPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [bidders, setBidders] = useState<BidderEntry[]>([]);
  const [stage, setStage] = useState<Stage>("idle");
  const [progress, setProgress] = useState<{ current: number; total: number; label: string } | null>(null);
  const [dragging, setDragging] = useState(false);

  function handleAddFiles(fileList: FileList | File[] | null) {
    if (!fileList) return;
    const incoming = Array.from(fileList);
    const accepted: BidderEntry[] = [];
    const rejected: string[] = [];
    for (const f of incoming) {
      if (!isZipFile(f)) {
        rejected.push(f.name);
        continue;
      }
      accepted.push({
        id: crypto.randomUUID(),
        name: deriveBidderName(f.name),
        file: f,
      });
    }
    if (accepted.length > 0) {
      setBidders((prev) => [...prev, ...accepted]);
      toast.success(
        accepted.length === 1
          ? `Added ${accepted[0].name}`
          : `Added ${accepted.length} bidder archives`
      );
    }
    if (rejected.length > 0) {
      toast.error(
        `Skipped ${rejected.length} non-ZIP file${rejected.length > 1 ? "s" : ""}: ${rejected.slice(0, 3).join(", ")}${rejected.length > 3 ? "…" : ""}`
      );
    }
  }

  function handleDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setDragging(false);
    if (stage !== "idle") return;
    handleAddFiles(e.dataTransfer.files);
  }

  function handleRemoveBidder(bid: string) {
    setBidders((prev) => prev.filter((b) => b.id !== bid));
  }

  async function handleEvaluate() {
    if (bidders.length === 0) {
      toast.error("Add at least one bidder before evaluating.");
      return;
    }
    setStage("uploading");
    try {
      for (let i = 0; i < bidders.length; i++) {
        const b = bidders[i];
        setProgress({ current: i + 1, total: bidders.length, label: `Uploading ${b.name}…` });
        await uploadBidder(id, b.file, b.name);
      }
      setStage("evaluating");
      setProgress({ current: bidders.length, total: bidders.length, label: "Running evaluation against approved criteria…" });
      await evaluateTender(id);
      toast.success("Evaluation complete — viewing matrix");
      router.push(`/tender/${id}/matrix`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Evaluation failed";
      toast.error(message);
      setStage("idle");
      setProgress(null);
    }
  }

  const evaluating = stage !== "idle";

  return (
    <div className="max-w-3xl mx-auto w-full px-6 py-8">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Upload Bidder Documents</h1>
      <p className="text-slate-500 text-sm mb-8">
        Upload each bidder&apos;s ZIP archive (containing their PDF submissions). The evaluator will process each against the approved criteria.
      </p>

      {/* Drop area */}
      <Card
        className={`border-2 border-dashed mb-6 transition-colors ${
          dragging ? "border-primary bg-primary/5" : "border-slate-200"
        }`}
      >
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Add Bidder Archives</CardTitle>
          <CardDescription>
            Drop one or more ZIP archives, or click to select multiple. Each ZIP should contain a bidder&apos;s financial, technical, and compliance documents.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <label
            className="flex flex-col items-center justify-center gap-3 py-10 cursor-pointer group"
            onDragOver={(e) => { e.preventDefault(); if (stage === "idle") setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
          >
            <div className={`h-12 w-12 rounded-full flex items-center justify-center transition-colors ${
              dragging ? "bg-primary/10" : "bg-slate-100 group-hover:bg-primary/10"
            }`}>
              <FileArchive className={`h-6 w-6 transition-colors ${
                dragging ? "text-primary" : "text-slate-400 group-hover:text-primary"
              }`} />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-slate-700">
                Drop bidder ZIPs here or click to select multiple
              </p>
              <p className="text-xs text-slate-400 mt-1">
                Accepts .zip archives — hold ⌘ / Ctrl in the picker to select several at once
              </p>
            </div>
            <input
              type="file"
              accept=".zip,application/zip"
              multiple
              className="hidden"
              disabled={stage !== "idle"}
              onChange={(e) => {
                handleAddFiles(e.target.files);
                e.target.value = "";
              }}
            />
          </label>
        </CardContent>
      </Card>

      {/* Bidder list */}
      {bidders.length > 0 && (
        <BidderUploadList bidders={bidders} onRemove={handleRemoveBidder} />
      )}

      {/* Live progress */}
      {progress && (
        <div className="mt-6 p-4 bg-white border border-primary/20 rounded-xl">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-slate-700">{progress.label}</p>
            <p className="text-xs text-slate-500">
              {progress.current} / {progress.total}
            </p>
          </div>
          <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all"
              style={{ width: `${(progress.current / progress.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mt-8">
        <p className="text-sm text-slate-500">
          {bidders.length === 0 ? "No bidders added yet" : `${bidders.length} bidder${bidders.length > 1 ? "s" : ""} ready for evaluation`}
        </p>
        <Button
          onClick={handleEvaluate}
          disabled={bidders.length === 0 || evaluating}
          className="gap-2"
        >
          {stage === "uploading" ? (
            <>
              <Upload className="h-4 w-4 animate-bounce" />
              Uploading…
            </>
          ) : stage === "evaluating" ? (
            <>
              <Upload className="h-4 w-4 animate-bounce" />
              Evaluating…
            </>
          ) : (
            <>
              Run Evaluation
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
