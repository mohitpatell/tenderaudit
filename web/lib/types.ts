export interface BBox {
  page: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export type CriterionType = 'financial' | 'technical' | 'compliance' | 'documentation';
export type ThresholdOp = '>=' | '<=' | '==' | 'exists' | 'not_blacklisted';
export type VerdictLabel = 'Eligible' | 'NotEligible' | 'NeedsManualReview';

export interface Criterion {
  id: string;
  name: string;
  type: CriterionType;
  description: string;
  threshold_value: number | null;
  threshold_unit: string | null;
  threshold_operator: ThresholdOp;
  source_clause: string;
  source_bbox: BBox | null;
  required_documents: string[];
  is_mandatory: boolean;
  approved?: boolean;
}

export interface BidderDoc {
  id: string;
  bidder_id: string;
  filename: string;
  doc_type: string | null;
  blob_id: string;
}

export interface Bidder {
  id: string;
  tender_id: string;
  name: string;
  documents: BidderDoc[];
}

export interface Evidence {
  bidder_doc_id: string;
  page: number;
  bbox: BBox;
  quote: string;
  score: number;
}

export interface Verdict {
  criterion_id: string;
  bidder_id: string;
  verdict: VerdictLabel;
  confidence: number;
  explanation: string;
  evidence: Evidence[];
}

export interface Tender {
  id: string;
  title: string;
  issuer: string;
  nit_number: string | null;
  estimated_value: number | null;
  criteria: Criterion[];
}

export interface EvaluationMatrix {
  tender_id: string;
  bidders: Bidder[];
  criteria: Criterion[];
  verdicts: Verdict[];
}

export interface AuditEntry {
  id: string;
  tender_id: string;
  action: string;
  actor: string;
  timestamp: string;
  details: Record<string, unknown>;
}

export interface TenderSummary {
  id: string;
  title: string | null;
  issuer: string | null;
  nit_number: string | null;
  criteria_count: number;
  bidder_count: number;
  verdict_count: number;
  not_eligible_count: number;
  manual_review_count: number;
}

export interface BidderSummary {
  id: string;
  tender_id: string;
  name: string | null;
  doc_count: number;
}

export interface AuditRow {
  id: number;
  ts: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  payload_json: string;
  prev_hash: string;
  this_hash: string;
}

export interface AuditChainStatus {
  valid: boolean;
  broken_at: number | null;
}
