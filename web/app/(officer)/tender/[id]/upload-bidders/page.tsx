"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Upload, ArrowRight, FileArchive } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { BidderUploadList } from "@/components/BidderUploadList";

interface BidderEntry {
  id: string;
  name: string;
  file: File;
}

export default function UploadBiddersPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [bidders, setBidders] = useState<BidderEntry[]>([]);
  const [evaluating, setEvaluating] = useState(false);

  function handleAddBidder(file: File) {
    const name = file.name.replace(/\.(zip|pdf)$/i, "").replace(/[-_]/g, " ");
    setBidders((prev) => [...prev, { id: crypto.randomUUID(), name, file }]);
  }

  function handleRemoveBidder(bid: string) {
    setBidders((prev) => prev.filter((b) => b.id !== bid));
  }

  async function handleEvaluate() {
    if (bidders.length === 0) {
      toast.error("Add at least one bidder before evaluating.");
      return;
    }
    setEvaluating(true);
    // Simulate evaluation time
    await new Promise((r) => setTimeout(r, 1500));
    toast.success("Evaluation complete — viewing matrix");
    router.push(`/tender/${id}/matrix`);
  }

  return (
    <div className="max-w-3xl mx-auto w-full px-6 py-8">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Upload Bidder Documents</h1>
      <p className="text-slate-500 text-sm mb-8">
        Upload each bidder&apos;s ZIP archive (containing their PDF submissions). The evaluator will process each against the approved criteria.
      </p>

      {/* Drop area */}
      <Card className="border-2 border-dashed border-slate-200 mb-6">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Add Bidder Archive</CardTitle>
          <CardDescription>Each ZIP should contain the bidder&apos;s financial, technical, and compliance documents</CardDescription>
        </CardHeader>
        <CardContent>
          <label className="flex flex-col items-center justify-center gap-3 py-10 cursor-pointer group">
            <div className="h-12 w-12 rounded-full bg-slate-100 group-hover:bg-primary/10 flex items-center justify-center transition-colors">
              <FileArchive className="h-6 w-6 text-slate-400 group-hover:text-primary transition-colors" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-slate-700">Drop bidder ZIP here or click to browse</p>
              <p className="text-xs text-slate-400 mt-1">Accepts .zip archives</p>
            </div>
            <input
              type="file"
              accept=".zip,application/zip"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleAddBidder(f);
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

      <div className="flex items-center justify-between mt-8">
        <p className="text-sm text-slate-500">
          {bidders.length === 0 ? "No bidders added yet" : `${bidders.length} bidder${bidders.length > 1 ? "s" : ""} ready for evaluation`}
        </p>
        <Button
          onClick={handleEvaluate}
          disabled={bidders.length === 0 || evaluating}
          className="gap-2"
        >
          {evaluating ? (
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

      {/* Skip to demo */}
      <div className="mt-4 text-center">
        <button
          className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
          onClick={() => router.push(`/tender/${id}/matrix`)}
        >
          Skip — view demo matrix
        </button>
      </div>
    </div>
  );
}
