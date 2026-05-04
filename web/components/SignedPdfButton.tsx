"use client";

import { useState } from "react";
import { Shield, Loader2, Download } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { signTender } from "@/lib/api";

interface SignedPdfButtonProps {
  tenderId: string;
}

export function SignedPdfButton({ tenderId }: SignedPdfButtonProps) {
  const [loading, setLoading] = useState(false);

  async function handleSign() {
    setLoading(true);
    try {
      const { url } = await signTender(tenderId);
      // Open in new tab with download
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit-${tenderId}.pdf`;
      a.target = "_blank";
      a.click();
      toast.success("Signed audit PDF generated");
    } catch {
      toast.info("Backend offline — signed PDF not available");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button
      variant="outline"
      onClick={handleSign}
      disabled={loading}
      className="gap-2 border-primary/30 text-primary hover:bg-primary/5"
    >
      {loading ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin" />
          Generating…
        </>
      ) : (
        <>
          <Shield className="h-4 w-4" />
          Generate signed audit PDF
          <Download className="h-3.5 w-3.5" />
        </>
      )}
    </Button>
  );
}
