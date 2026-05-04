"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowRight, CheckCircle, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { CriterionCard } from "@/components/CriterionCard";
import { getTender } from "@/lib/api";
import { MOCK_CRITERIA, MOCK_TENDER } from "@/lib/mock";
import type { Criterion, Tender } from "@/lib/types";

export default function CriteriaPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [tender, setTender] = useState<Tender | null>(null);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [approved, setApproved] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const t = await getTender(id);
        setTender(t);
        const crit = t.criteria.length > 0 ? t.criteria : MOCK_CRITERIA;
        setCriteria(crit);
      } catch {
        setTender(MOCK_TENDER);
        setCriteria(MOCK_CRITERIA);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  function handleApprove(cid: string) {
    setApproved((prev) => new Set([...prev, cid]));
  }

  function handleUpdate(updated: Criterion) {
    setCriteria((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  }

  const allApproved = criteria.length > 0 && approved.size === criteria.length;

  function continueToUpload() {
    if (!allApproved) {
      toast.error("Please approve all criteria before continuing.");
      return;
    }
    toast.success("Criteria approved — upload bidder documents");
    router.push(`/tender/${id}/upload-bidders`);
  }

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto w-full px-6 py-8 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-48" />
        {[1, 2, 3].map((i) => <Skeleton key={i} className="h-48 w-full rounded-xl" />)}
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto w-full px-6 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-slate-500 mb-6">
        <span>{tender?.issuer}</span>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="text-slate-700 font-medium">{tender?.nit_number || id}</span>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="text-primary font-medium">Review Criteria</span>
      </div>

      <div className="flex items-start justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1">{tender?.title}</h1>
          <p className="text-slate-500 text-sm">
            Review and approve the {criteria.length} eligibility criteria extracted from the tender.
            You can edit thresholds and required documents before approving.
          </p>
        </div>
        <Button
          onClick={continueToUpload}
          disabled={!allApproved}
          className="flex-shrink-0 gap-2"
        >
          <CheckCircle className="h-4 w-4" />
          Approve all &amp; continue
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>

      {/* Progress */}
      <div className="flex items-center gap-3 mb-6 text-sm">
        <div className="flex-1 bg-slate-200 rounded-full h-2">
          <div
            className="bg-primary h-2 rounded-full transition-all duration-300"
            style={{ width: `${criteria.length > 0 ? (approved.size / criteria.length) * 100 : 0}%` }}
          />
        </div>
        <span className="text-slate-500 font-medium">{approved.size} / {criteria.length} approved</span>
      </div>

      {/* Criteria list */}
      <div className="space-y-4">
        {criteria.map((c) => (
          <CriterionCard
            key={c.id}
            criterion={c}
            isApproved={approved.has(c.id)}
            onApprove={() => handleApprove(c.id)}
            onUpdate={handleUpdate}
          />
        ))}
      </div>

      {/* Bottom CTA */}
      {allApproved && (
        <div className="mt-8 p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-2 text-emerald-800">
            <CheckCircle className="h-5 w-5 text-emerald-600" />
            <span className="font-medium">All {criteria.length} criteria approved</span>
          </div>
          <Button onClick={continueToUpload} className="gap-2 bg-emerald-600 hover:bg-emerald-700">
            Upload bidder documents
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
