import type { EvaluationMatrix, Tender } from "./types";
import { MOCK_MATRIX, MOCK_TENDER } from "./mock";

const PROXY = "/api/proxy";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const url = `${PROXY}/${path.replace(/^\//, "")}`;
  const res = await fetch(url, opts);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function uploadTender(file: File): Promise<{ id: string }> {
  const form = new FormData();
  form.append("file", file);
  return request<{ id: string }>("api/tenders/upload", {
    method: "POST",
    body: form,
  });
}

export async function getTender(id: string): Promise<Tender> {
  try {
    return await request<Tender>(`api/tenders/${id}`);
  } catch {
    if (id === "crpf-1" || id === "mock") return MOCK_TENDER;
    throw new Error(`Tender ${id} not found`);
  }
}

export async function getMatrix(tenderId: string): Promise<EvaluationMatrix> {
  try {
    return await request<EvaluationMatrix>(`api/tenders/${tenderId}/matrix`);
  } catch {
    if (tenderId === "crpf-1" || tenderId === "mock") return MOCK_MATRIX;
    return { ...MOCK_MATRIX, tender_id: tenderId };
  }
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
