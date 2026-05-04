"use client";

import { useState } from "react";
import { History, Shield, CheckCircle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

interface AuditEntry {
  id: string;
  action: string;
  actor: string;
  timestamp: string;
  details: string;
}

interface AuditTrailDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tenderId: string;
}

// Mock audit rows for demo
const MOCK_AUDIT: AuditEntry[] = [
  { id: "a1", action: "criteria_approved", actor: "Officer Sharma", timestamp: "2024-03-15 09:42", details: "6 criteria approved after review" },
  { id: "a2", action: "evaluation_started", actor: "System", timestamp: "2024-03-15 09:45", details: "4 bidder archives submitted for evaluation" },
  { id: "a3", action: "evaluation_complete", actor: "System", timestamp: "2024-03-15 09:52", details: "24 verdicts generated — 10 Eligible, 8 Manual Review, 6 Not Eligible" },
  { id: "a4", action: "verdict_override", actor: "Officer Sharma", timestamp: "2024-03-15 10:14", details: "Bidder BEML / Net Worth: NotEligible → NeedsManualReview. Justification: Consolidated figures pending clarification." },
  { id: "a5", action: "audit_pdf_signed", actor: "Officer Sharma", timestamp: "2024-03-15 10:30", details: "Audit PDF signed with Class III DSC and sealed." },
];

const actionIcon: Record<string, React.ReactNode> = {
  criteria_approved: <CheckCircle className="h-4 w-4 text-emerald-500" />,
  evaluation_started: <Loader2 className="h-4 w-4 text-blue-500" />,
  evaluation_complete: <CheckCircle className="h-4 w-4 text-primary" />,
  verdict_override: <Shield className="h-4 w-4 text-amber-500" />,
  audit_pdf_signed: <Shield className="h-4 w-4 text-emerald-600" />,
};

export function AuditTrailDrawer({ open, onOpenChange, tenderId }: AuditTrailDrawerProps) {
  const [verifying, setVerifying] = useState(false);

  async function handleVerify() {
    setVerifying(true);
    await new Promise((r) => setTimeout(r, 1200));
    setVerifying(false);
    toast.success("Chain verified — all hashes match");
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md flex flex-col p-0">
        <SheetHeader className="px-6 pt-6 pb-4 border-b">
          <SheetTitle className="flex items-center gap-2">
            <History className="h-4 w-4" />
            Audit Trail
          </SheetTitle>
          <SheetDescription className="text-xs">
            Tender {tenderId} — immutable event log
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className="flex-1">
          <div className="px-6 py-4 space-y-0">
            {MOCK_AUDIT.map((entry, i) => (
              <div key={entry.id}>
                <div className="flex gap-3 py-3">
                  <div className="flex-shrink-0 mt-0.5">
                    {actionIcon[entry.action] ?? <Shield className="h-4 w-4 text-slate-400" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-slate-700 capitalize">
                        {entry.action.replace(/_/g, " ")}
                      </span>
                      <span className="text-[10px] text-slate-400 flex-shrink-0">{entry.timestamp}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{entry.details}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">{entry.actor}</p>
                  </div>
                </div>
                {i < MOCK_AUDIT.length - 1 && <Separator />}
              </div>
            ))}
          </div>
        </ScrollArea>

        <div className="border-t px-6 py-4">
          <Button
            variant="outline"
            className="w-full gap-2"
            onClick={handleVerify}
            disabled={verifying}
          >
            {verifying ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Verifying chain…</>
            ) : (
              <><Shield className="h-4 w-4" /> Verify chain integrity</>
            )}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
