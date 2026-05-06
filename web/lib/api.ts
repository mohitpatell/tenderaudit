import type {
  AuditChainStatus,
  AuditRow,
  Bidder,
  BidderSummary,
  EvaluationMatrix,
  Tender,
  TenderSummary,
} from "./types";
import { MOCK_MATRIX, MOCK_TENDER } from "./mock";

const PROXY = "/api/proxy";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const url = `${PROXY}/${path.replace(/^\//, "")}`;
  const res = await fetch(url, opts);
  if (!res.ok) {
    throw new ApiError(res.status, `API error ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function uploadTender(file: File): Promise<{ id: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await request<{ tender: Tender; blob_id: string }>(
    "api/tenders/upload",
    { method: "POST", body: form },
  );
  return { id: res.tender.id };
}

export async function getTender(id: string): Promise<Tender> {
  try {
    return await request<Tender>(`api/tenders/${id}`);
  } catch {
    if (id === "mock") return MOCK_TENDER;
    throw new Error(`Tender ${id} not found`);
  }
}

export async function getMatrix(tenderId: string): Promise<EvaluationMatrix | null> {
  try {
    return await request<EvaluationMatrix>(`api/tenders/${tenderId}/matrix`);
  } catch (err) {
    if (tenderId === "mock") return MOCK_MATRIX;
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export async function uploadBidder(
  tenderId: string,
  file: File,
  bidderName: string
): Promise<{ bidder: Bidder }> {
  const form = new FormData();
  form.append("file", file);
  form.append("bidder_name", bidderName);
  return request<{ bidder: Bidder }>(`api/tenders/${tenderId}/bidders/upload`, {
    method: "POST",
    body: form,
  });
}

export async function evaluateTender(tenderId: string): Promise<EvaluationMatrix> {
  return request<EvaluationMatrix>(`api/tenders/${tenderId}/evaluate`, {
    method: "POST",
  });
}

export async function approveCriteria(
  tenderId: string,
  criteriaIds: string[]
): Promise<void> {
  await request(`api/tenders/${tenderId}/criteria/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ criteria_ids: criteriaIds }),
  });
}

export async function submitAuditOverride(
  tenderId: string,
  bidderId: string,
  criterionId: string,
  verdict: string,
  justification: string
): Promise<void> {
  await request(`api/audit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tender_id: tenderId,
      bidder_id: bidderId,
      criterion_id: criterionId,
      verdict,
      justification,
    }),
  });
}

export async function signTender(tenderId: string): Promise<{ blob_id: string; url: string }> {
  return request<{ blob_id: string; url: string }>(`api/tenders/${tenderId}/sign`, {
    method: "POST",
  });
}

export async function listTenders(): Promise<TenderSummary[]> {
  return request<TenderSummary[]>("api/tenders");
}

export async function listBidders(tenderId: string): Promise<BidderSummary[]> {
  return request<BidderSummary[]>(`api/tenders/${tenderId}/bidders`);
}

export async function listAllAudit(limit = 200): Promise<AuditRow[]> {
  const res = await request<{ rows: AuditRow[] }>(`api/audit?limit=${limit}`);
  return res.rows;
}

export async function verifyAuditChain(): Promise<AuditChainStatus> {
  return request<AuditChainStatus>("api/audit/verify");
}
