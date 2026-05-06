"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Pencil, FileText, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { SplitPane } from "@/components/SplitPane";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getMatrix, submitAuditOverride } from "@/lib/api";
import { verdictBgClass, verdictDotClass, verdictLabel } from "@/lib/utils";
import type { Verdict, Criterion, Bidder, Evidence, VerdictLabel } from "@/lib/types";

export default function DrillDownPage() {
  const { bidId, critId } = useParams<{ bidId: string; critId: string }>();

  const [loading, setLoading] = useState(true);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [criterion, setCriterion] = useState<Criterion | null>(null);
  const [bidder, setBidder] = useState<Bidder | null>(null);
  const [tenderId, setTenderId] = useState<string>("crpf-1");

  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideVerdict, setOverrideVerdict] = useState<VerdictLabel>("Eligible");
  const [overrideJustification, setOverrideJustification] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    try {
      const matrix = await getMatrix("crpf-1");
      if (!matrix) return;
      setTenderId(matrix.tender_id);
      const v = matrix.verdicts.find((v) => v.bidder_id === bidId && v.criterion_id === critId);
      const c = matrix.criteria.find((c) => c.id === critId);
      const b = matrix.bidders.find((b) => b.id === bidId);
      setVerdict(v ?? null);
      setCriterion(c ?? null);
      setBidder(b ?? null);
    } finally {
      setLoading(false);
    }
  }, [bidId, critId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleOverrideSubmit() {
    if (!overrideJustification.trim()) {
      toast.error("Justification is required for manual override.");
      return;
    }
    setSubmitting(true);
    try {
      await submitAuditOverride(tenderId, bidId, critId, overrideVerdict, overrideJustification);
      toast.success("Override recorded in audit trail.");
      setOverrideOpen(false);
      // Optimistic update
      if (verdict) {
        setVerdict({ ...verdict, verdict: overrideVerdict });
      }
    } catch {
      toast.info("Backend offline — override noted locally.");
      setOverrideOpen(false);
      if (verdict) {
        setVerdict({ ...verdict, verdict: overrideVerdict });
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex-1 p-8 space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-96 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </div>
    );
  }

  if (!verdict || !criterion || !bidder) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-slate-400">Verdict not found for this bidder / criterion pair.</p>
      </div>
    );
  }

  const rightPane = (
    <div className="h-full overflow-auto p-6 space-y-4">
      {/* Back link */}
      <Link
        href={`/tender/${tenderId}/matrix`}
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-primary transition-colors mb-2"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to matrix
      </Link>

      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-xs text-slate-400 flex-wrap">
        <span>{bidder.name}</span>
        <ChevronRight className="h-3 w-3" />
        <span>{criterion.name}</span>
      </div>

      {/* Criterion card */}
      <Card className="border-slate-200">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <CardTitle className="text-base">{criterion.name}</CardTitle>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium
              ${criterion.type === "financial" ? "bg-blue-50 text-blue-700" :
                criterion.type === "technical" ? "bg-purple-50 text-purple-700" :
                criterion.type === "compliance" ? "bg-orange-50 text-orange-700" :
                "bg-slate-50 text-slate-700"}`}>
              {criterion.type}
            </span>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-slate-600">{criterion.description}</p>
          {criterion.threshold_value !== null && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-slate-500">Threshold:</span>
              <code className="bg-slate-100 px-2 py-0.5 rounded text-slate-800 text-xs">
                {criterion.threshold_operator} {criterion.threshold_value.toLocaleString("en-IN")}{" "}
                {criterion.threshold_unit}
              </code>
            </div>
          )}
          <blockquote className="border-l-2 border-primary/30 pl-3 text-xs text-slate-500 italic">
            {criterion.source_clause}
          </blockquote>
        </CardContent>
      </Card>

      {/* Verdict card */}
      <Card className={`border ${verdictBgClass(verdict.verdict)}`}>
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${verdictDotClass(verdict.verdict)}`} />
              <span className="font-semibold">{verdictLabel(verdict.verdict)}</span>
            </div>
            <div className="flex items-center gap-2">
              <ConfidenceBadge confidence={verdict.confidence} />
              <Button
                size="sm"
                variant="outline"
                className="h-7 gap-1.5 text-xs"
                onClick={() => {
                  setOverrideVerdict(verdict.verdict);
                  setOverrideOpen(true);
                }}
              >
                <Pencil className="h-3 w-3" />
                Override
              </Button>
            </div>
          </div>
          <p className="text-sm leading-relaxed">{verdict.explanation}</p>
        </CardContent>
      </Card>

      {/* Evidence list */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">
          Evidence ({verdict.evidence.length})
        </h3>
        <div className="space-y-3">
          {verdict.evidence.map((ev: Evidence, i: number) => {
            const doc = bidder.documents.find((d) => d.id === ev.bidder_doc_id);
            return (
              <Card key={i} className="border-slate-200">
                <CardContent className="pt-4 pb-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileText className="h-3.5 w-3.5 text-slate-400" />
                      <span className="text-xs font-medium text-slate-600">
                        {doc?.filename ?? ev.bidder_doc_id}
                      </span>
                      <span className="text-xs text-slate-400">p.{ev.page}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-slate-400">Score</span>
                      <div className="w-16 bg-slate-200 rounded-full h-1.5">
                        <div
                          className="h-1.5 rounded-full bg-primary transition-all"
                          style={{ width: `${ev.score * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-500">{(ev.score * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  <blockquote className="border-l-2 border-cyan-400 pl-3 text-sm text-slate-700 leading-relaxed bg-slate-50 rounded-r py-2">
                    &ldquo;{ev.quote}&rdquo;
                  </blockquote>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );

  // For the PDF viewer left pane, we use a placeholder since no real blob URL is available
  const leftPane = (
    <div className="h-full flex flex-col items-center justify-center gap-4 bg-slate-100 text-slate-400 p-8">
      <FileText className="h-16 w-16 text-slate-300" />
      <div className="text-center">
        <p className="font-medium text-slate-500">Bidder PDF Viewer</p>
        <p className="text-sm mt-1">
          {bidder.documents[0]?.filename ?? "No document"}
        </p>
        <p className="text-xs mt-2 text-slate-400">
          Connect backend on :8001 to view PDF with evidence highlights
        </p>
      </div>
      {verdict.evidence[0] && (
        <div className="bg-white rounded-lg border p-3 text-xs text-slate-600 max-w-sm text-center">
          <p className="font-medium mb-1">Evidence location</p>
          <p>Page {verdict.evidence[0].page} · bbox ({verdict.evidence[0].bbox.x0.toFixed(0)}, {verdict.evidence[0].bbox.y0.toFixed(0)})</p>
        </div>
      )}
    </div>
  );

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <SplitPane left={leftPane} right={rightPane} defaultLeftPercent={50} />

      {/* Override dialog */}
      <Dialog open={overrideOpen} onOpenChange={setOverrideOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Override Verdict</DialogTitle>
            <DialogDescription>
              Manual overrides are recorded in the immutable audit trail with your identity and timestamp.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>New Verdict</Label>
              <Select value={overrideVerdict} onValueChange={(v) => setOverrideVerdict(v as VerdictLabel)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Eligible">Eligible</SelectItem>
                  <SelectItem value="NotEligible">Not Eligible</SelectItem>
                  <SelectItem value="NeedsManualReview">Needs Manual Review</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>
                Justification <span className="text-rose-500">*</span>
              </Label>
              <Textarea
                placeholder="Provide a detailed reason for the override — this will appear in the audit trail and signed PDF…"
                rows={4}
                value={overrideJustification}
                onChange={(e) => setOverrideJustification(e.target.value)}
              />
              <p className="text-xs text-slate-400">Minimum 20 characters required</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOverrideOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleOverrideSubmit}
              disabled={submitting || overrideJustification.trim().length < 20}
            >
              {submitting ? "Submitting…" : "Submit Override"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
