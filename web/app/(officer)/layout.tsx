import { Shield } from "lucide-react";
import Link from "next/link";

export default function OfficerLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-white border-b h-14 flex items-center px-6 gap-4 sticky top-0 z-20 shadow-sm">
        <Link href="/" className="flex items-center gap-2.5 mr-4">
          <div className="h-7 w-7 rounded bg-primary flex items-center justify-center">
            <Shield className="h-4 w-4 text-white" />
          </div>
          <span className="font-semibold text-slate-900">TenderAudit</span>
        </Link>
        <div className="h-5 w-px bg-slate-200" />
        <span className="text-sm text-slate-500">Procurement Evaluation</span>
      </header>
      <main className="flex-1 flex flex-col">{children}</main>
    </div>
  );
}
