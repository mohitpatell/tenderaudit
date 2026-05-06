"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  FileText,
  Hash,
  Link2,
  ScrollText,
  Shield,
  ShieldCheck,
  ShieldX,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  listAllAudit,
  listBidders,
  listTenders,
  verifyAuditChain,
} from "@/lib/api";
import { truncate } from "@/lib/utils";
import type {
  AuditChainStatus,
  AuditRow,
  BidderSummary,
  TenderSummary,
} from "@/lib/types";

function shortHash(hash: string, len = 8): string {
  if (!hash) return "—";
  return hash.slice(0, len);
}

function formatTs(ts: string): string {
  try {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return ts;
    return d.toLocaleString();
  } catch {
    return ts;
  }
}

function prettyJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

function actionBadgeVariant(action: string): "default" | "secondary" | "destructive" | "outline" {
  if (action.startsWith("tender.evaluate") || action.startsWith("tender.sign")) return "default";
  if (action.startsWith("bidder.")) return "secondary";
  if (action.includes("override") || action.includes("delete")) return "destructive";
  return "outline";
}

export default function DataExplorerPage() {
  const [tenders, setTenders] = useState<TenderSummary[] | null>(null);
  const [tendersError, setTendersError] = useState<string | null>(null);

  const [auditRows, setAuditRows] = useState<AuditRow[] | null>(null);
  const [auditError, setAuditError] = useState<string | null>(null);

  const [chainStatus, setChainStatus] = useState<AuditChainStatus | null>(null);
  const [chainError, setChainError] = useState<string | null>(null);

  const [selectedTenderId, setSelectedTenderId] = useState<string | null>(null);
  const [bidders, setBidders] = useState<BidderSummary[] | null>(null);
  const [biddersLoading, setBiddersLoading] = useState(false);
  const [biddersError, setBiddersError] = useState<string | null>(null);

  const [selectedAudit, setSelectedAudit] = useState<AuditRow | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const t = await listTenders();
        if (!cancelled) setTenders(t);
      } catch (err) {
        if (!cancelled) {
          setTenders([]);
          setTendersError(err instanceof Error ? err.message : "Failed to load tenders");
        }
      }
      try {
        const a = await listAllAudit(200);
        if (!cancelled) setAuditRows(a);
      } catch (err) {
        if (!cancelled) {
          setAuditRows([]);
          setAuditError(err instanceof Error ? err.message : "Failed to load audit log");
        }
      }
      try {
        const c = await verifyAuditChain();
        if (!cancelled) setChainStatus(c);
      } catch (err) {
        if (!cancelled) {
          setChainError(err instanceof Error ? err.message : "Could not verify chain");
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedTenderId) {
      setBidders(null);
      return;
    }
    let cancelled = false;
    setBiddersLoading(true);
    setBiddersError(null);
    listBidders(selectedTenderId)
      .then((b) => {
        if (!cancelled) setBidders(b);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setBidders([]);
          setBiddersError(err instanceof Error ? err.message : "Failed to load bidders");
        }
      })
      .finally(() => {
        if (!cancelled) setBiddersLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedTenderId]);

  const latestHash = useMemo(() => {
    if (!auditRows || auditRows.length === 0) return null;
    return auditRows[0].this_hash;
  }, [auditRows]);

  const auditCount = auditRows?.length ?? 0;

  return (
    <TooltipProvider delayDuration={150}>
      <div className="min-h-screen bg-slate-50">
        {/* Header */}
        <header className="bg-white border-b h-14 flex items-center px-6 gap-4 sticky top-0 z-20 shadow-sm">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded bg-primary flex items-center justify-center">
              <Shield className="h-4 w-4 text-white" />
            </div>
            <span className="font-semibold text-slate-900">TenderAudit</span>
          </Link>
          <div className="h-5 w-px bg-slate-200" />
          <span className="text-sm text-slate-500 flex items-center gap-1.5">
            <Database className="h-3.5 w-3.5" />
            Data &amp; Audit Explorer
          </span>
          <div className="ml-auto">
            {chainStatus?.valid ? (
              <Badge
                variant="outline"
                className="bg-emerald-50 text-emerald-700 border-emerald-200 gap-1.5"
              >
                <ShieldCheck className="h-3 w-3" />
                Chain verified
              </Badge>
            ) : chainStatus && !chainStatus.valid ? (
              <Badge
                variant="outline"
                className="bg-rose-50 text-rose-700 border-rose-200 gap-1.5"
              >
                <ShieldX className="h-3 w-3" />
                Chain broken
              </Badge>
            ) : null}
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">
          {/* Title block */}
          <div>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
              Data &amp; Audit Explorer
            </h1>
            <p className="text-slate-500 mt-1.5 max-w-3xl">
              Every tender, every bidder, every verdict, every audit entry — and proof
              that the audit chain hasn&apos;t been tampered with.
            </p>
          </div>

          {/* Chain status card */}
          <ChainStatusCard
            status={chainStatus}
            error={chainError}
            count={auditCount}
            latestHash={latestHash}
          />

          {/* Tabs */}
          <Tabs defaultValue="tenders" className="space-y-4">
            <TabsList className="bg-white border h-auto p-1">
              <TabsTrigger value="tenders" className="gap-1.5">
                <FileText className="h-3.5 w-3.5" /> Tenders
                {tenders && (
                  <Badge variant="outline" className="ml-1 px-1.5 py-0 text-[10px]">
                    {tenders.length}
                  </Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="bidders" className="gap-1.5">
                <Users className="h-3.5 w-3.5" /> Bidders
              </TabsTrigger>
              <TabsTrigger value="audit" className="gap-1.5">
                <ScrollText className="h-3.5 w-3.5" /> Audit Log
                {auditRows && (
                  <Badge variant="outline" className="ml-1 px-1.5 py-0 text-[10px]">
                    {auditRows.length}
                  </Badge>
                )}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="tenders">
              <TendersTable tenders={tenders} error={tendersError} />
            </TabsContent>

            <TabsContent value="bidders">
              <BiddersPanel
                tenders={tenders}
                selectedTenderId={selectedTenderId}
                onSelectTender={setSelectedTenderId}
                bidders={bidders}
                loading={biddersLoading}
                error={biddersError}
              />
            </TabsContent>

            <TabsContent value="audit">
              <AuditTable
                rows={auditRows}
                error={auditError}
                onSelect={setSelectedAudit}
              />
            </TabsContent>
          </Tabs>
        </main>

        {/* Audit detail dialog */}
        <Dialog
          open={selectedAudit !== null}
          onOpenChange={(open) => {
            if (!open) setSelectedAudit(null);
          }}
        >
          <DialogContent className="max-w-2xl">
            {selectedAudit && (
              <>
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <ScrollText className="h-4 w-4 text-primary" />
                    Audit row #{selectedAudit.id}
                  </DialogTitle>
                  <DialogDescription>
                    {formatTs(selectedAudit.ts)} · {selectedAudit.actor} ·{" "}
                    {selectedAudit.action}
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <KvField label="Entity type" value={selectedAudit.entity_type} />
                    <KvField label="Entity ID" value={selectedAudit.entity_id} mono />
                  </div>
                  <div className="grid grid-cols-1 gap-2 text-xs">
                    <KvField
                      label="Prev hash"
                      value={selectedAudit.prev_hash}
                      mono
                      wrap
                    />
                    <KvField
                      label="This hash"
                      value={selectedAudit.this_hash}
                      mono
                      wrap
                    />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                      Payload
                    </div>
                    <pre className="bg-slate-900 text-slate-100 rounded-md p-3 text-xs font-mono overflow-auto max-h-80 leading-relaxed">
                      {prettyJson(selectedAudit.payload_json)}
                    </pre>
                  </div>
                </div>
              </>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}

interface KvFieldProps {
  label: string;
  value: string;
  mono?: boolean;
  wrap?: boolean;
}

function KvField({ label, value, mono, wrap }: KvFieldProps) {
  return (
    <div>
      <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide mb-0.5">
        {label}
      </div>
      <div
        className={
          (mono ? "font-mono " : "") +
          (wrap ? "break-all " : "") +
          "text-slate-800"
        }
      >
        {value}
      </div>
    </div>
  );
}

interface ChainStatusCardProps {
  status: AuditChainStatus | null;
  error: string | null;
  count: number;
  latestHash: string | null;
}

function ChainStatusCard({ status, error, count, latestHash }: ChainStatusCardProps) {
  if (error) {
    return (
      <Card className="border-rose-200 bg-rose-50">
        <CardContent className="p-4 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-rose-600 mt-0.5" />
          <div>
            <div className="font-semibold text-rose-900">
              Could not verify audit chain
            </div>
            <div className="text-sm text-rose-700">{error}</div>
          </div>
        </CardContent>
      </Card>
    );
  }
  if (status === null) {
    return (
      <Card>
        <CardContent className="p-4 flex items-center gap-3">
          <Skeleton className="h-9 w-9 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-72" />
            <Skeleton className="h-3 w-48" />
          </div>
        </CardContent>
      </Card>
    );
  }
  if (status.valid) {
    return (
      <Card className="border-emerald-200 bg-emerald-50/60">
        <CardContent className="p-4 flex items-start gap-3">
          <div className="h-9 w-9 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
            <ShieldCheck className="h-5 w-5 text-emerald-700" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-700" />
              <span className="font-semibold text-emerald-900">
                Audit chain verified
              </span>
              <Badge
                variant="outline"
                className="bg-white border-emerald-200 text-emerald-800"
              >
                SHA-256
              </Badge>
            </div>
            <div className="text-sm text-emerald-800/80 mt-0.5">
              {count} {count === 1 ? "row" : "rows"}, all hashes link correctly back to
              genesis.
            </div>
            {latestHash && (
              <div className="mt-2 text-xs text-emerald-900/70 flex items-center gap-1.5">
                <Hash className="h-3 w-3" />
                <span>Latest hash:</span>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <code className="font-mono bg-white/60 border border-emerald-200 rounded px-1.5 py-0.5">
                      {shortHash(latestHash, 12)}…
                    </code>
                  </TooltipTrigger>
                  <TooltipContent className="font-mono text-xs max-w-md break-all">
                    {latestHash}
                  </TooltipContent>
                </Tooltip>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="border-rose-200 bg-rose-50">
      <CardContent className="p-4 flex items-start gap-3">
        <div className="h-9 w-9 rounded-full bg-rose-100 flex items-center justify-center flex-shrink-0">
          <ShieldX className="h-5 w-5 text-rose-700" />
        </div>
        <div>
          <div className="font-semibold text-rose-900">
            Audit chain BROKEN at row #{status.broken_at}
          </div>
          <div className="text-sm text-rose-700 mt-0.5">
            One or more rows fail SHA-256 verification. The log has been tampered with
            or corrupted.
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface TendersTableProps {
  tenders: TenderSummary[] | null;
  error: string | null;
}

function TendersTable({ tenders, error }: TendersTableProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Tenders in memory</CardTitle>
        <CardDescription>
          In-memory store on the API process. Click an ID to open its evaluation matrix.
        </CardDescription>
      </CardHeader>
      <CardContent className="px-0 pb-0">
        {error && (
          <div className="mx-6 mb-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {error}
          </div>
        )}
        {tenders === null ? (
          <div className="px-6 pb-6 space-y-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </div>
        ) : tenders.length === 0 ? (
          <EmptyState
            icon={<FileText className="h-6 w-6" />}
            title="No tenders uploaded yet"
            description="Upload one from the home page to populate this view."
            actionHref="/"
            actionLabel="Go to home"
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Title</TableHead>
                <TableHead className="text-right">Criteria</TableHead>
                <TableHead className="text-right">Bidders</TableHead>
                <TableHead className="text-right">Verdicts</TableHead>
                <TableHead className="text-right">NotEligible</TableHead>
                <TableHead className="text-right">Manual</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tenders.map((t) => {
                const target = t.verdict_count > 0
                  ? `/tender/${t.id}/matrix`
                  : `/tender/${t.id}/criteria`;
                return (
                <TableRow key={t.id}>
                  <TableCell>
                    <Link
                      href={target}
                      className="font-mono text-xs text-primary hover:underline inline-flex items-center gap-1"
                    >
                      {t.id}
                      <Link2 className="h-3 w-3" />
                    </Link>
                  </TableCell>
                  <TableCell>
                    <div className="font-medium text-slate-900">
                      {t.title || <span className="text-slate-400">Untitled</span>}
                    </div>
                    <div className="text-xs text-slate-500">
                      {t.issuer || "—"}
                      {t.nit_number ? ` · ${t.nit_number}` : ""}
                    </div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {t.criteria_count}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {t.bidder_count}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {t.verdict_count}
                  </TableCell>
                  <TableCell className="text-right">
                    {t.not_eligible_count > 0 ? (
                      <Badge
                        variant="outline"
                        className="bg-rose-50 border-rose-200 text-rose-700 tabular-nums"
                      >
                        {t.not_eligible_count}
                      </Badge>
                    ) : (
                      <span className="text-slate-400 tabular-nums">0</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {t.manual_review_count > 0 ? (
                      <Badge
                        variant="outline"
                        className="bg-amber-50 border-amber-200 text-amber-700 tabular-nums"
                      >
                        {t.manual_review_count}
                      </Badge>
                    ) : (
                      <span className="text-slate-400 tabular-nums">0</span>
                    )}
                  </TableCell>
                </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

interface BiddersPanelProps {
  tenders: TenderSummary[] | null;
  selectedTenderId: string | null;
  onSelectTender: (id: string) => void;
  bidders: BidderSummary[] | null;
  loading: boolean;
  error: string | null;
}

function BiddersPanel({
  tenders,
  selectedTenderId,
  onSelectTender,
  bidders,
  loading,
  error,
}: BiddersPanelProps) {
  const tenderOptions = tenders ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Bidders by tender</CardTitle>
        <CardDescription>
          Select a tender to see uploaded bidder bundles and their document counts.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="max-w-md">
          <Select
            value={selectedTenderId ?? undefined}
            onValueChange={onSelectTender}
            disabled={tenderOptions.length === 0}
          >
            <SelectTrigger>
              <SelectValue
                placeholder={
                  tenderOptions.length === 0
                    ? "No tenders available"
                    : "Select a tender…"
                }
              />
            </SelectTrigger>
            <SelectContent>
              {tenderOptions.map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  <span className="font-medium">{t.title || "Untitled"}</span>
                  <span className="text-slate-400 ml-2 font-mono text-xs">
                    {t.id}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {error && (
          <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {error}
          </div>
        )}

        {!selectedTenderId ? (
          <EmptyState
            icon={<Users className="h-6 w-6" />}
            title="Select a tender to view bidders"
            description="Bidder bundles are stored per-tender in memory."
          />
        ) : loading ? (
          <div className="space-y-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </div>
        ) : !bidders || bidders.length === 0 ? (
          <EmptyState
            icon={<Users className="h-6 w-6" />}
            title="No bidders for this tender"
            description="Upload bidder bundles from the tender's bidder upload page."
          />
        ) : (
          <div className="-mx-6 border-t">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead className="text-right">Documents</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {bidders.map((b) => (
                  <TableRow key={b.id}>
                    <TableCell className="font-mono text-xs">{b.id}</TableCell>
                    <TableCell className="font-medium text-slate-900">
                      {b.name || <span className="text-slate-400">Unnamed</span>}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {b.doc_count}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface AuditTableProps {
  rows: AuditRow[] | null;
  error: string | null;
  onSelect: (row: AuditRow) => void;
}

function AuditTable({ rows, error, onSelect }: AuditTableProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Audit log</CardTitle>
        <CardDescription>
          Hash-chained, append-only. Each row links to the previous row&apos;s SHA-256.
          Click a row to inspect its payload.
        </CardDescription>
      </CardHeader>
      <CardContent className="px-0 pb-0">
        {error && (
          <div className="mx-6 mb-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {error}
          </div>
        )}
        {rows === null ? (
          <div className="px-6 pb-6 space-y-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={<ScrollText className="h-6 w-6" />}
            title="No audit entries yet"
            description="Upload a tender, evaluate it, or sign a matrix to generate audit rows."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">#</TableHead>
                <TableHead>Time</TableHead>
                <TableHead>Actor</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Entity</TableHead>
                <TableHead>Payload</TableHead>
                <TableHead>Hash</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow
                  key={r.id}
                  className="cursor-pointer"
                  onClick={() => onSelect(r)}
                >
                  <TableCell className="font-mono text-xs text-slate-500 tabular-nums">
                    {r.id}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-xs text-slate-600">
                    {formatTs(r.ts)}
                  </TableCell>
                  <TableCell className="text-xs">{r.actor}</TableCell>
                  <TableCell>
                    <Badge variant={actionBadgeVariant(r.action)} className="font-mono text-[10px]">
                      {r.action}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs">
                    <div className="text-slate-700">{r.entity_type}</div>
                    <div className="font-mono text-[10px] text-slate-400">
                      {r.entity_id}
                    </div>
                  </TableCell>
                  <TableCell>
                    <code className="font-mono text-[11px] text-slate-600 bg-slate-50 border border-slate-200 rounded px-1.5 py-0.5">
                      {truncate(r.payload_json, 80)}
                    </code>
                  </TableCell>
                  <TableCell>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <code className="font-mono text-[10px] bg-slate-50 border border-slate-200 rounded px-1.5 py-0.5">
                          {shortHash(r.this_hash, 8)}
                        </code>
                      </TooltipTrigger>
                      <TooltipContent
                        className="font-mono text-xs max-w-md break-all"
                        side="left"
                      >
                        {r.this_hash}
                      </TooltipContent>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  actionHref?: string;
  actionLabel?: string;
}

function EmptyState({
  icon,
  title,
  description,
  actionHref,
  actionLabel,
}: EmptyStateProps) {
  return (
    <div className="px-6 py-12 flex flex-col items-center text-center">
      <div className="h-12 w-12 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center mb-3">
        {icon}
      </div>
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      <p className="text-sm text-slate-500 mt-1 max-w-sm">{description}</p>
      {actionHref && actionLabel && (
        <Link
          href={actionHref}
          className="mt-4 text-sm text-primary hover:underline inline-flex items-center gap-1"
        >
          {actionLabel}
          <Link2 className="h-3 w-3" />
        </Link>
      )}
    </div>
  );
}
