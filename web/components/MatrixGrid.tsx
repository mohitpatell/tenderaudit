"use client";

import { TooltipProvider } from "@/components/ui/tooltip";
import { VerdictCell } from "@/components/VerdictCell";
import { cn } from "@/lib/utils";
import type { EvaluationMatrix, Verdict } from "@/lib/types";

interface MatrixGridProps {
  matrix: EvaluationMatrix;
  onCellClick: (bidderId: string, criterionId: string) => void;
}

const typeColor: Record<string, string> = {
  financial: "bg-blue-50 text-blue-700",
  technical: "bg-purple-50 text-purple-700",
  compliance: "bg-orange-50 text-orange-700",
  documentation: "bg-slate-100 text-slate-600",
};

export function MatrixGrid({ matrix, onCellClick }: MatrixGridProps) {
  const { bidders, criteria, verdicts } = matrix;

  function getVerdict(bidderId: string, criterionId: string): Verdict | undefined {
    return verdicts.find((v) => v.bidder_id === bidderId && v.criterion_id === criterionId);
  }

  return (
    <TooltipProvider delayDuration={300}>
      <div className="w-full overflow-auto rounded-xl border bg-white shadow-sm">
        {/* Sticky header + sticky first column via CSS grid */}
        <div
          className="grid"
          style={{
            gridTemplateColumns: `200px repeat(${criteria.length}, 120px)`,
          }}
        >
          {/* Top-left corner cell */}
          <div className="sticky left-0 top-0 z-30 bg-slate-50 border-b border-r p-3 flex items-end">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Bidder</span>
          </div>

          {/* Criterion header cells */}
          {criteria.map((c) => (
            <div
              key={c.id}
              className="sticky top-0 z-20 bg-slate-50 border-b border-r p-2 min-w-[120px]"
            >
              <div className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded-full mb-1 w-fit", typeColor[c.type])}>
                {c.type}
              </div>
              <p className="text-xs font-semibold text-slate-800 leading-tight line-clamp-2">{c.name}</p>
              {c.threshold_value !== null && (
                <p className="text-[10px] text-slate-400 mt-0.5">
                  {c.threshold_operator} {c.threshold_value.toLocaleString("en-IN")} {c.threshold_unit}
                </p>
              )}
              {c.is_mandatory && (
                <span className="text-[9px] text-rose-600 font-medium">mandatory</span>
              )}
            </div>
          ))}

          {/* Data rows */}
          {bidders.map((bidder, rowIdx) => (
            <>
              {/* Sticky bidder name cell */}
              <div
                key={`name-${bidder.id}`}
                className={cn(
                  "sticky left-0 z-10 border-b border-r p-3 flex flex-col justify-center",
                  rowIdx % 2 === 0 ? "bg-white" : "bg-slate-50/50"
                )}
              >
                <span className="text-sm font-semibold text-slate-800 line-clamp-1">{bidder.name}</span>
                <span className="text-xs text-slate-400 mt-0.5">
                  {bidder.documents.length} doc{bidder.documents.length !== 1 ? "s" : ""}
                </span>
              </div>

              {/* Verdict cells */}
              {criteria.map((c) => {
                const v = getVerdict(bidder.id, c.id);
                return (
                  <div
                    key={`cell-${bidder.id}-${c.id}`}
                    className={cn(
                      "border-b border-r p-2 flex items-center justify-center",
                      rowIdx % 2 === 0 ? "bg-white" : "bg-slate-50/30"
                    )}
                  >
                    {v ? (
                      <VerdictCell verdict={v} onClick={() => onCellClick(bidder.id, c.id)} />
                    ) : (
                      <div className="w-[120px] h-[80px] rounded-md border border-dashed border-slate-200 flex items-center justify-center">
                        <span className="text-xs text-slate-300">—</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </>
          ))}
        </div>
      </div>
    </TooltipProvider>
  );
}
