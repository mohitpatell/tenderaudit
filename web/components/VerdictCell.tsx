"use client";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn, verdictDotClass, verdictLabel, truncate } from "@/lib/utils";
import type { Verdict } from "@/lib/types";

interface VerdictCellProps {
  verdict: Verdict;
  onClick: () => void;
  width?: number;
  height?: number;
}

const cellBg: Record<string, string> = {
  Eligible: "bg-emerald-50 hover:bg-emerald-100 border-emerald-200",
  NotEligible: "bg-rose-50 hover:bg-rose-100 border-rose-200",
  NeedsManualReview: "bg-amber-50 hover:bg-amber-100 border-amber-200",
};

const confBarColor: Record<string, string> = {
  Eligible: "bg-emerald-400",
  NotEligible: "bg-rose-400",
  NeedsManualReview: "bg-amber-400",
};

export function VerdictCell({ verdict, onClick }: VerdictCellProps) {
  const isLowConf = verdict.confidence < 0.7;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={onClick}
          className={cn(
            "w-[120px] h-[80px] border rounded-md flex flex-col items-start justify-between p-2.5",
            "transition-colors duration-150 cursor-pointer select-none",
            "active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            cellBg[verdict.verdict],
            isLowConf && "animate-pulse-border border-2"
          )}
        >
          {/* Top: dot + label */}
          <div className="flex items-center gap-1.5">
            <span className={cn("h-2 w-2 rounded-full flex-shrink-0", verdictDotClass(verdict.verdict))} />
            <span className="text-xs font-medium text-slate-700 leading-tight">
              {verdictLabel(verdict.verdict)}
            </span>
          </div>

          {/* Confidence bar (bottom) */}
          <div className="w-full">
            <div className="w-full bg-white/60 rounded-full h-1">
              <div
                className={cn("h-1 rounded-full transition-all", confBarColor[verdict.verdict])}
                style={{ width: `${verdict.confidence * 100}%` }}
              />
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">{(verdict.confidence * 100).toFixed(0)}%</div>
          </div>
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[260px]">
        <p className="text-xs leading-relaxed">{truncate(verdict.explanation, 200)}</p>
      </TooltipContent>
    </Tooltip>
  );
}
