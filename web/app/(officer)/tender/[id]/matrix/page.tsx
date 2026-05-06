"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronRight, FileText, LayoutGrid, FileArchive } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { MatrixGrid } from "@/components/MatrixGrid";
import { SignedPdfButton } from "@/components/SignedPdfButton";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { getMatrix } from "@/lib/api";
import type { EvaluationMatrix, Verdict, VerdictLabel } from "@/lib/types";

export default function MatrixPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [matrix, setMatrix] = useState<EvaluationMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedVerdict, setSelectedVerdict] = useState<Verdict | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const m = await getMatrix(id);
        setMatrix(m);
      } catch (err) {
        console.error("Failed to load matrix", err);
        setMatrix(null);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  function handleCellClick(bidderId: string, criterionId: string) {
    // Open quick drawer OR navigate to drill-down
    const verdict = matrix?.verdicts.find(
      (v) => v.bidder_id === bidderId && v.criterion_id === criterionId
    );
    if (verdict) {
      setSelectedVerdict(verdict);
      setDrawerOpen(true);
    }
  }

  function handleViewFullContext() {
    if (!selectedVerdict) return;
    setDrawerOpen(false);
    router.push(`/bidder/${selectedVerdict.bidder_id}/criterion/${selectedVerdict.criterion_id}`);
  }

  // Stats
  const stats = matrix
    ? matrix.verdicts.reduce(
        (acc, v) => {
          acc[v.verdict] = (acc[v.verdict] ?? 0) + 1;
          return acc;
        },
        {} as Record<VerdictLabel, number>
      )
    : null;

  if (loading) {
    return (
      <div className="flex-1 p-8 space-y-4">
        <Skeleton className="h-8 w-80" />
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-96 w-full rounded-xl" />
      </div>
    );
  }

  if (!matrix || matrix.verdicts.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="max-w-md text-center space-y-4">
          <div className="h-16 w-16 mx-auto rounded-full bg-slate-100 flex items-center justify-center">
            <LayoutGrid className="h-8 w-8 text-slate-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-slate-900">No evaluation yet</h2>
            <p className="text-sm text-slate-500 mt-1">
              Upload bidder ZIP archives to run the evaluator against the approved criteria. The matrix will populate from real verdicts — nothing here is precomputed.
            </p>
          </div>
          <Button asChild className="gap-2">
            <Link href={`/tender/${id}/upload-bidders`}>
              <FileArchive className="h-4 w-4" />
              Upload Bidders
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  const tender = {
    id,
    title: "Supply of Armoured Vehicles — CRPF NIT-71/2024",
    issuer: "CRPF",
    nit: "CRPF/NIT-71/2024",
  };

  return (
    <div className="flex-1 flex flex-col">
      {/* Page header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-2">
          <span>{tender.issuer}</span>
          <ChevronRight className="h-3.5 w-3.5" />
          <span>{tender.nit}</span>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-primary font-medium flex items-center gap-1">
            <LayoutGrid className="h-3.5 w-3.5" />
            Evaluation Matrix
          </span>
        </div>

        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900">{tender.title}</h1>
            <div className="flex items-center gap-4 mt-1">
              <Link
                href={`/tender/${id}/criteria`}
                className="text-xs text-slate-500 hover:text-primary transition-colors flex items-center gap-1"
              >
                <FileText className="h-3 w-3" />
                View criteria
              </Link>
              {stats && (
                <div className="flex items-center gap-3 text-xs">
                  <span className="flex items-center gap-1 text-emerald-700">
                    <span className="h-2 w-2 rounded-full bg-emerald-500" />
                    {stats.Eligible ?? 0} Eligible
                  </span>
                  <span className="flex items-center gap-1 text-amber-700">
                    <span className="h-2 w-2 rounded-full bg-amber-500" />
                    {stats.NeedsManualReview ?? 0} Need Review
                  </span>
                  <span className="flex items-center gap-1 text-rose-700">
                    <span className="h-2 w-2 rounded-full bg-rose-500" />
                    {stats.NotEligible ?? 0} Not Eligible
                  </span>
                </div>
              )}
            </div>
          </div>

          <SignedPdfButton tenderId={id} />
        </div>
      </div>

      {/* Matrix */}
      <div className="flex-1 overflow-auto p-6">
        <MatrixGrid matrix={matrix} onCellClick={handleCellClick} />

        {/* Summary */}
        {stats && (
          <div className="mt-6 p-4 bg-white border rounded-xl flex flex-wrap gap-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-slate-900">{matrix.bidders.length}</div>
              <div className="text-xs text-slate-500 mt-0.5">Total Bidders</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-emerald-600">{stats.Eligible ?? 0}</div>
              <div className="text-xs text-slate-500 mt-0.5">Eligible</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-amber-600">{stats.NeedsManualReview ?? 0}</div>
              <div className="text-xs text-slate-500 mt-0.5">Need Review</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-rose-600">{stats.NotEligible ?? 0}</div>
              <div className="text-xs text-slate-500 mt-0.5">Not Eligible</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-slate-700">{matrix.criteria.length}</div>
              <div className="text-xs text-slate-500 mt-0.5">Criteria</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-slate-700">{matrix.verdicts.length}</div>
              <div className="text-xs text-slate-500 mt-0.5">Total Verdicts</div>
            </div>
          </div>
        )}
      </div>

      {/* Evidence drawer (quick peek) */}
      {selectedVerdict && (
        <EvidenceDrawer
          open={drawerOpen}
          onOpenChange={setDrawerOpen}
          verdict={selectedVerdict}
          criterion={matrix.criteria.find((c) => c.id === selectedVerdict.criterion_id)}
          bidder={matrix.bidders.find((b) => b.id === selectedVerdict.bidder_id)}
          onViewFullContext={handleViewFullContext}
        />
      )}
    </div>
  );
}
