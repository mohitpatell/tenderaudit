"use client";

import { ExternalLink, FileText } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { verdictBgClass, verdictDotClass, verdictLabel } from "@/lib/utils";
import type { Verdict, Criterion, Bidder } from "@/lib/types";

interface EvidenceDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  verdict: Verdict;
  criterion?: Criterion;
  bidder?: Bidder;
  onViewFullContext: () => void;
}

export function EvidenceDrawer({
  open,
  onOpenChange,
  verdict,
  criterion,
  bidder,
  onViewFullContext,
}: EvidenceDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg flex flex-col p-0">
        <SheetHeader className="px-6 pt-6 pb-4 border-b">
          <SheetTitle className="text-base">
            {criterion?.name ?? "Evidence"}
          </SheetTitle>
          <SheetDescription className="text-xs">
            {bidder?.name} · Quick evidence preview
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className="flex-1">
          <div className="px-6 py-4 space-y-4">
            {/* Verdict chip */}
            <div className={`rounded-lg border p-3 ${verdictBgClass(verdict.verdict)}`}>
              <div className="flex items-center gap-2 mb-1.5">
                <span className={`h-2.5 w-2.5 rounded-full ${verdictDotClass(verdict.verdict)}`} />
                <span className="font-semibold text-sm">{verdictLabel(verdict.verdict)}</span>
                <ConfidenceBadge confidence={verdict.confidence} className="ml-auto" />
              </div>
              <p className="text-sm leading-relaxed">{verdict.explanation}</p>
            </div>

            {/* Criterion summary */}
            {criterion && (
              <div className="space-y-1">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Source Clause</p>
                <blockquote className="border-l-2 border-primary/30 pl-3 text-xs text-slate-600 italic">
                  {criterion.source_clause}
                </blockquote>
              </div>
            )}

            <Separator />

            {/* Evidence list */}
            <div className="space-y-3">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Evidence ({verdict.evidence.length})
              </p>
              {verdict.evidence.map((ev, i) => {
                const doc = bidder?.documents.find((d) => d.id === ev.bidder_doc_id);
                return (
                  <div key={i} className="rounded-lg border border-slate-200 p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5 text-slate-400" />
                        <span className="text-xs text-slate-600 font-medium">
                          {doc?.filename ?? ev.bidder_doc_id}
                        </span>
                        <span className="text-xs text-slate-400">p.{ev.page}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div className="w-12 bg-slate-200 rounded-full h-1">
                          <div
                            className="h-1 rounded-full bg-primary"
                            style={{ width: `${ev.score * 100}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-slate-400">{(ev.score * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                    <blockquote className="text-xs text-slate-700 leading-relaxed border-l-2 border-cyan-300 pl-2.5 bg-slate-50 py-1.5 rounded-r">
                      &ldquo;{ev.quote}&rdquo;
                    </blockquote>
                  </div>
                );
              })}
            </div>
          </div>
        </ScrollArea>

        {/* Footer */}
        <div className="border-t px-6 py-4">
          <Button onClick={onViewFullContext} className="w-full gap-2">
            <ExternalLink className="h-4 w-4" />
            View full PDF context
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
