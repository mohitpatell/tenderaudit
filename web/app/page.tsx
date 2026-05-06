"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Shield, FileText, CheckCircle, BookOpen, ArrowRight, Building2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { UploadDropzone } from "@/components/UploadDropzone";
import { listTenders, uploadTender } from "@/lib/api";
import type { TenderSummary } from "@/lib/types";

export default function LandingPage() {
  const router = useRouter();
  const [uploading, setUploading] = useState(false);
  const [pastTenders, setPastTenders] = useState<TenderSummary[]>([]);
  const [tendersLoading, setTendersLoading] = useState(true);

  useEffect(() => {
    listTenders()
      .then((rows) => setPastTenders(rows))
      .catch(() => setPastTenders([]))
      .finally(() => setTendersLoading(false));
  }, []);

  async function handleTenderUpload(file: File) {
    setUploading(true);
    try {
      const { id } = await uploadTender(file);
      toast.success("Tender uploaded — extracting criteria…");
      router.push(`/tender/${id}/criteria`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload failed";
      toast.error(message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-md bg-primary flex items-center justify-center">
              <Shield className="h-5 w-5 text-white" />
            </div>
            <span className="font-semibold text-lg text-slate-900">TenderAudit</span>
            <span className="text-xs text-slate-400 border border-slate-200 rounded px-1.5 py-0.5 ml-1">BETA</span>
          </div>
          <nav className="flex items-center gap-4 text-sm text-slate-600">
            <a href="#features" className="hover:text-slate-900 transition-colors">Features</a>
            <a href="#demo" className="hover:text-slate-900 transition-colors">Demo</a>
            <Link
              href="/data"
              className="text-sm text-muted-foreground hover:text-primary transition-colors"
            >
              View stored data &amp; audit log →
            </Link>
            <Button size="sm" variant="outline">Sign in</Button>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 bg-slate-100 border border-slate-200 rounded-full px-4 py-1.5 text-sm text-slate-600 mb-6">
          <Shield className="h-3.5 w-3.5 text-primary" />
          Designed for Government Procurement Officers
        </div>
        <h1 className="text-5xl font-bold text-slate-900 leading-tight mb-4 max-w-3xl mx-auto">
          TenderAudit — the procurement evaluator that defends itself in writ court.
        </h1>
        <p className="text-xl text-slate-500 max-w-2xl mx-auto mb-12">
          Every verdict carries an evidence chain back to a bbox in a bidder PDF.
          No silent disqualification. No guesswork. Just auditable decisions.
        </p>

        {/* Upload area */}
        <div id="demo" className="max-w-2xl mx-auto mb-16">
          <Card className="border-2 border-dashed border-slate-200 shadow-none bg-slate-50/50">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold text-slate-800">Upload Tender PDF</CardTitle>
              <CardDescription>Upload the NIT/RFP document to extract eligibility criteria automatically</CardDescription>
            </CardHeader>
            <CardContent>
              <UploadDropzone
                accept={{ "application/pdf": [".pdf"] }}
                onFile={handleTenderUpload}
                loading={uploading}
                label="Drop tender PDF here or click to browse"
                sublabel="Supports NIT, RFP, and EOI documents"
              />
            </CardContent>
          </Card>
        </div>

        {/* Past tenders */}
        <div className="max-w-2xl mx-auto">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4 text-left">Recent Tenders</h2>
          {tendersLoading ? (
            <div className="text-sm text-slate-400 text-left">Loading…</div>
          ) : pastTenders.length === 0 ? (
            <div className="text-sm text-slate-400 text-left p-4 border border-dashed border-slate-200 rounded-xl">
              No tenders yet. Upload a tender PDF above to get started.
            </div>
          ) : (
            <div className="space-y-3">
              {pastTenders.map((t) => {
                const target = t.verdict_count > 0
                  ? `/tender/${t.id}/matrix`
                  : `/tender/${t.id}/criteria`;
                return (
                  <Card
                    key={t.id}
                    className="cursor-pointer hover:border-primary/40 hover:shadow-sm transition-all group"
                    onClick={() => router.push(target)}
                  >
                    <CardContent className="p-4 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="h-9 w-9 rounded bg-primary/10 flex items-center justify-center flex-shrink-0">
                          <FileText className="h-4 w-4 text-primary" />
                        </div>
                        <div className="text-left">
                          <p className="font-medium text-slate-900 text-sm">{t.title ?? "Untitled tender"}</p>
                          <p className="text-xs text-slate-500">
                            {[t.nit_number, t.issuer].filter(Boolean).join(" · ") || "—"}
                            {" · "}
                            {t.criteria_count} criteria
                            {t.bidder_count > 0 ? ` · ${t.bidder_count} bidder${t.bidder_count > 1 ? "s" : ""}` : ""}
                            {t.verdict_count > 0 ? ` · ${t.verdict_count} verdicts` : ""}
                          </p>
                        </div>
                      </div>
                      <ArrowRight className="h-4 w-4 text-slate-400 group-hover:text-primary transition-colors" />
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* Feature cards */}
      <section id="features" className="max-w-7xl mx-auto px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="border-0 bg-slate-50">
            <CardHeader>
              <div className="h-10 w-10 rounded-lg bg-emerald-100 flex items-center justify-center mb-2">
                <CheckCircle className="h-5 w-5 text-emerald-600" />
              </div>
              <CardTitle className="text-base">No silent disqualification — guaranteed</CardTitle>
              <CardDescription className="text-sm">
                Every &quot;Not Eligible&quot; verdict includes the exact clause, document, and page number that triggered it.
                Bidders can verify the reasoning themselves.
              </CardDescription>
            </CardHeader>
          </Card>

          <Card className="border-0 bg-slate-50">
            <CardHeader>
              <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center mb-2">
                <BookOpen className="h-5 w-5 text-blue-600" />
              </div>
              <CardTitle className="text-base">Evidence-backed verdicts</CardTitle>
              <CardDescription className="text-sm">
                LLM reads each bidder PDF, finds the relevant section, and extracts a verbatim quote
                with pixel-precise bounding box coordinates. Confidence scored per evidence piece.
              </CardDescription>
            </CardHeader>
          </Card>

          <Card className="border-0 bg-slate-50">
            <CardHeader>
              <div className="h-10 w-10 rounded-lg bg-purple-100 flex items-center justify-center mb-2">
                <Building2 className="h-5 w-5 text-purple-600" />
              </div>
              <CardTitle className="text-base">Digitally signed audit trail</CardTitle>
              <CardDescription className="text-sm">
                Generate a cryptographically signed PDF of the full evaluation matrix,
                immutable for RTI and court purposes. Every manual override is also recorded.
              </CardDescription>
            </CardHeader>
          </Card>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-slate-900 text-slate-400 py-8 mt-8">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-slate-500" />
            <span className="text-sm">TenderAudit — AI for Bharat Hackathon 2024</span>
          </div>
          <p className="text-xs text-slate-500">
            Built for government procurement transparency. Not for production use without compliance review.
          </p>
        </div>
      </footer>
    </div>
  );
}
