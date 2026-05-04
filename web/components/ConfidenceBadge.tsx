import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ConfidenceBadgeProps {
  confidence: number;
  className?: string;
}

export function ConfidenceBadge({ confidence, className }: ConfidenceBadgeProps) {
  const pct = Math.round(confidence * 100);
  const color =
    confidence >= 0.85
      ? "text-emerald-700 bg-emerald-50 border-emerald-200"
      : confidence >= 0.7
      ? "text-slate-600 bg-slate-50 border-slate-200"
      : "text-amber-700 bg-amber-50 border-amber-200";

  return (
    <Badge variant="outline" className={cn("font-mono text-xs", color, className)}>
      {pct}%
    </Badge>
  );
}
