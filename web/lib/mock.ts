import type { Tender, EvaluationMatrix, Criterion, Bidder, Verdict } from "./types";

export const MOCK_TENDER: Tender = {
  id: "crpf-1",
  title: "Supply of Armoured Vehicles — CRPF NIT-71/2024",
  issuer: "Central Reserve Police Force, Ministry of Home Affairs",
  nit_number: "CRPF/NIT-71/2024",
  estimated_value: 180000000,
  criteria: [],
};

export const MOCK_CRITERIA: Criterion[] = [
  {
    id: "c1",
    name: "Annual Turnover",
    type: "financial",
    description: "Bidder must have average annual turnover of at least INR 5 Cr over the last 3 financial years.",
    threshold_value: 50000000,
    threshold_unit: "INR",
    threshold_operator: ">=",
    source_clause: "Clause 12.1 — Financial Eligibility: The bidder shall have an average annual turnover of not less than INR 5,00,00,000 during the last three financial years.",
    source_bbox: { page: 3, x0: 72, y0: 210, x1: 540, y1: 260 },
    required_documents: ["Audited Balance Sheet (3 years)", "CA Certificate"],
    is_mandatory: true,
  },
  {
    id: "c2",
    name: "ISO 9001 Certification",
    type: "compliance",
    description: "Valid ISO 9001:2015 certification is required for manufacturing quality assurance.",
    threshold_value: null,
    threshold_unit: null,
    threshold_operator: "exists",
    source_clause: "Clause 14.3 — Quality Standards: Bidder must hold valid ISO 9001:2015 or equivalent certification.",
    source_bbox: { page: 5, x0: 72, y0: 140, x1: 540, y1: 180 },
    required_documents: ["ISO Certificate (valid)"],
    is_mandatory: true,
  },
  {
    id: "c3",
    name: "Prior Experience",
    type: "technical",
    description: "Minimum 5 years of experience in manufacturing or supplying armoured or special purpose vehicles.",
    threshold_value: 5,
    threshold_unit: "years",
    threshold_operator: ">=",
    source_clause: "Clause 13.2 — Technical Eligibility: The bidder shall have at least 5 years of experience in manufacturing or supply of armoured/special vehicles.",
    source_bbox: { page: 4, x0: 72, y0: 310, x1: 540, y1: 360 },
    required_documents: ["Work Order Copies", "Completion Certificates"],
    is_mandatory: true,
  },
  {
    id: "c4",
    name: "Blacklisting Check",
    type: "compliance",
    description: "Bidder must not be blacklisted by any central or state government authority.",
    threshold_value: null,
    threshold_unit: null,
    threshold_operator: "not_blacklisted",
    source_clause: "Clause 8.1 — Debarment: Firms debarred/blacklisted by any Government entity are not eligible to bid.",
    source_bbox: { page: 2, x0: 72, y0: 420, x1: 540, y1: 460 },
    required_documents: ["Self-declaration (non-blacklisting)"],
    is_mandatory: true,
  },
  {
    id: "c5",
    name: "Net Worth",
    type: "financial",
    description: "Net worth must be positive and not less than INR 2 Cr as of the last financial year.",
    threshold_value: 20000000,
    threshold_unit: "INR",
    threshold_operator: ">=",
    source_clause: "Clause 12.3 — Net Worth: The firm shall have a positive net worth of at least INR 2,00,00,000.",
    source_bbox: { page: 3, x0: 72, y0: 310, x1: 540, y1: 350 },
    required_documents: ["Audited Balance Sheet", "CA Certificate"],
    is_mandatory: false,
  },
  {
    id: "c6",
    name: "Class III DSC",
    type: "documentation",
    description: "Valid Class III Digital Signature Certificate required for submission.",
    threshold_value: null,
    threshold_unit: null,
    threshold_operator: "exists",
    source_clause: "Clause 6.2 — Electronic Submission: Bids must be digitally signed using a valid Class III DSC issued by a licensed CA.",
    source_bbox: { page: 1, x0: 72, y0: 510, x1: 540, y1: 550 },
    required_documents: ["DSC Certificate copy"],
    is_mandatory: true,
  },
];

export const MOCK_BIDDERS: Bidder[] = [
  {
    id: "bidder-a",
    tender_id: "crpf-1",
    name: "Mahindra Defence Systems",
    documents: [
      { id: "d1", bidder_id: "bidder-a", filename: "financials_mahindra.pdf", doc_type: "financial", blob_id: "blob-d1" },
      { id: "d2", bidder_id: "bidder-a", filename: "iso_cert_mahindra.pdf", doc_type: "compliance", blob_id: "blob-d2" },
    ],
  },
  {
    id: "bidder-b",
    tender_id: "crpf-1",
    name: "BEML Limited",
    documents: [
      { id: "d3", bidder_id: "bidder-b", filename: "financials_beml.pdf", doc_type: "financial", blob_id: "blob-d3" },
      { id: "d4", bidder_id: "bidder-b", filename: "experience_beml.pdf", doc_type: "technical", blob_id: "blob-d4" },
    ],
  },
  {
    id: "bidder-c",
    tender_id: "crpf-1",
    name: "Tata Advanced Systems",
    documents: [
      { id: "d5", bidder_id: "bidder-c", filename: "full_bid_tata.pdf", doc_type: null, blob_id: "blob-d5" },
    ],
  },
  {
    id: "bidder-d",
    tender_id: "crpf-1",
    name: "Force Motors Ltd",
    documents: [
      { id: "d6", bidder_id: "bidder-d", filename: "bid_force_motors.pdf", doc_type: null, blob_id: "blob-d6" },
    ],
  },
];

// 24 verdicts: 10 Eligible, 6 NotEligible, 8 NeedsManualReview
export const MOCK_VERDICTS: Verdict[] = [
  // Bidder A (Mahindra) — mostly eligible
  { criterion_id: "c1", bidder_id: "bidder-a", verdict: "Eligible", confidence: 0.95, explanation: "Mahindra Defence Systems reported average annual turnover of INR 847 Cr over FY21-23, well exceeding the INR 5 Cr threshold. Audited financials confirm.", evidence: [{ bidder_doc_id: "d1", page: 2, bbox: { page: 2, x0: 100, y0: 200, x1: 500, y1: 230 }, quote: "Average annual turnover: INR 847,23,45,000 for FY 2021-22 to 2023-24", score: 0.97 }] },
  { criterion_id: "c2", bidder_id: "bidder-a", verdict: "Eligible", confidence: 0.98, explanation: "ISO 9001:2015 certificate found, issued by Bureau Veritas, valid until March 2026.", evidence: [{ bidder_doc_id: "d2", page: 1, bbox: { page: 1, x0: 80, y0: 100, x1: 480, y1: 180 }, quote: "ISO 9001:2015 Certificate No: BV-IND-2023-Q-4521, valid until 31 March 2026", score: 0.99 }] },
  { criterion_id: "c3", bidder_id: "bidder-a", verdict: "Eligible", confidence: 0.92, explanation: "Mahindra has been manufacturing armoured vehicles since 1997, providing over 26 years of experience.", evidence: [{ bidder_doc_id: "d1", page: 4, bbox: { page: 4, x0: 72, y0: 310, x1: 540, y1: 350 }, quote: "Incorporated armoured vehicle division in 1997; 26 years of continuous manufacturing experience.", score: 0.91 }] },
  { criterion_id: "c4", bidder_id: "bidder-a", verdict: "Eligible", confidence: 0.99, explanation: "Self-declaration found. No record in MHA blacklist database.", evidence: [{ bidder_doc_id: "d1", page: 8, bbox: { page: 8, x0: 72, y0: 400, x1: 540, y1: 430 }, quote: "We hereby declare that our firm has not been blacklisted by any government authority.", score: 0.98 }] },
  { criterion_id: "c5", bidder_id: "bidder-a", verdict: "Eligible", confidence: 0.96, explanation: "Net worth of INR 1,240 Cr as of 31 March 2024, far exceeds INR 2 Cr requirement.", evidence: [{ bidder_doc_id: "d1", page: 3, bbox: { page: 3, x0: 72, y0: 280, x1: 540, y1: 310 }, quote: "Net worth as on 31.03.2024: INR 1240,45,23,000", score: 0.95 }] },
  { criterion_id: "c6", bidder_id: "bidder-a", verdict: "Eligible", confidence: 0.99, explanation: "Class III DSC certificate submitted, issued by eMudhra, valid.", evidence: [{ bidder_doc_id: "d2", page: 1, bbox: { page: 1, x0: 72, y0: 50, x1: 400, y1: 80 }, quote: "DSC Class III — eMudhra Certificate Authority — Valid until 2025-12-31", score: 0.99 }] },

  // Bidder B (BEML) — shortfall on turnover
  { criterion_id: "c1", bidder_id: "bidder-b", verdict: "NotEligible", confidence: 0.91, explanation: "BEML's average turnover for rail division submitted was INR 3.2 Cr which falls short of the INR 5 Cr threshold. Defence segment turnover not separately certified.", evidence: [{ bidder_doc_id: "d3", page: 2, bbox: { page: 2, x0: 100, y0: 200, x1: 500, y1: 230 }, quote: "Turnover (Defence segment) FY2022-24 average: INR 3,21,45,000", score: 0.89 }] },
  { criterion_id: "c2", bidder_id: "bidder-b", verdict: "Eligible", confidence: 0.97, explanation: "ISO 9001:2015 certificate for manufacturing plant found, valid until 2025.", evidence: [{ bidder_doc_id: "d3", page: 5, bbox: { page: 5, x0: 72, y0: 120, x1: 480, y1: 170 }, quote: "ISO 9001:2015 — DNV Certificate — Plant: Bangalore — Valid: Dec 2025", score: 0.97 }] },
  { criterion_id: "c3", bidder_id: "bidder-b", verdict: "Eligible", confidence: 0.88, explanation: "BEML has supplied special vehicles to Indian Railways and Defence since 1964, exceeding 5-year requirement.", evidence: [{ bidder_doc_id: "d4", page: 1, bbox: { page: 1, x0: 72, y0: 100, x1: 540, y1: 140 }, quote: "BEML's defence vehicle division established 1964; supplied to Army, CRPF, BSF.", score: 0.87 }] },
  { criterion_id: "c4", bidder_id: "bidder-b", verdict: "Eligible", confidence: 0.99, explanation: "Declaration submitted. BEML is a Navratna PSU, no debarment.", evidence: [{ bidder_doc_id: "d3", page: 9, bbox: { page: 9, x0: 72, y0: 380, x1: 540, y1: 410 }, quote: "BEML Limited hereby declares non-blacklisting status as per MHA records.", score: 0.99 }] },
  { criterion_id: "c5", bidder_id: "bidder-b", verdict: "NeedsManualReview", confidence: 0.65, explanation: "Net worth figure in submission appears to be for parent company, not the bidding entity. Clarification needed on whether defence division figures are standalone.", evidence: [{ bidder_doc_id: "d3", page: 3, bbox: { page: 3, x0: 72, y0: 290, x1: 540, y1: 320 }, quote: "Consolidated net worth: INR 2,340 Cr. Standalone defence segment net worth: data not provided.", score: 0.61 }] },
  { criterion_id: "c6", bidder_id: "bidder-b", verdict: "Eligible", confidence: 0.99, explanation: "DSC certificate found, Class III, valid.", evidence: [{ bidder_doc_id: "d3", page: 1, bbox: { page: 1, x0: 72, y0: 60, x1: 400, y1: 90 }, quote: "Digital Signature Certificate — Class III — BEML Limited — Valid 2026", score: 0.99 }] },

  // Bidder C (Tata) — missing ISO
  { criterion_id: "c1", bidder_id: "bidder-c", verdict: "Eligible", confidence: 0.93, explanation: "Tata Advanced Systems turnover of INR 42 Cr (defence segment) qualifies.", evidence: [{ bidder_doc_id: "d5", page: 3, bbox: { page: 3, x0: 72, y0: 200, x1: 540, y1: 240 }, quote: "Defence segment turnover FY22-24 average: INR 42,18,00,000", score: 0.92 }] },
  { criterion_id: "c2", bidder_id: "bidder-c", verdict: "NotEligible", confidence: 0.88, explanation: "ISO 9001:2015 certificate not found in submission. An ISO 14001 (environmental) certificate was submitted but does not meet the quality management requirement.", evidence: [{ bidder_doc_id: "d5", page: 7, bbox: { page: 7, x0: 72, y0: 150, x1: 540, y1: 190 }, quote: "ISO 14001:2015 Environmental Certificate — Tata Advanced Systems — Valid 2025", score: 0.62 }] },
  { criterion_id: "c3", bidder_id: "bidder-c", verdict: "Eligible", confidence: 0.90, explanation: "TASL has been operational in defence systems since 2007, providing 16+ years of experience.", evidence: [{ bidder_doc_id: "d5", page: 2, bbox: { page: 2, x0: 72, y0: 100, x1: 540, y1: 140 }, quote: "TASL was incorporated in 2007 with a focus on defence aerospace and land systems.", score: 0.89 }] },
  { criterion_id: "c4", bidder_id: "bidder-c", verdict: "Eligible", confidence: 0.99, explanation: "Non-blacklisting declaration provided. Tata group entity with clean record.", evidence: [{ bidder_doc_id: "d5", page: 10, bbox: { page: 10, x0: 72, y0: 400, x1: 540, y1: 430 }, quote: "Tata Advanced Systems Limited affirms it has not been blacklisted by any Government.", score: 0.99 }] },
  { criterion_id: "c5", bidder_id: "bidder-c", verdict: "NeedsManualReview", confidence: 0.62, explanation: "Net worth certificate provided but signed by internal CA rather than independent chartered accountant. Needs verification.", evidence: [{ bidder_doc_id: "d5", page: 4, bbox: { page: 4, x0: 72, y0: 290, x1: 540, y1: 320 }, quote: "Net worth certificate prepared by CFO office — INR 18,40,00,000 as on 31.03.2024", score: 0.58 }] },
  { criterion_id: "c6", bidder_id: "bidder-c", verdict: "NeedsManualReview", confidence: 0.68, explanation: "DSC certificate was submitted but the certificate number doesn't match a recognized CA. Manual verification recommended.", evidence: [{ bidder_doc_id: "d5", page: 1, bbox: { page: 1, x0: 72, y0: 60, x1: 400, y1: 90 }, quote: "DSC Class III — Certificate No: CERT-TAS-2024-221 — unclear issuing authority", score: 0.64 }] },

  // Bidder D (Force Motors) — ambiguous across criteria
  { criterion_id: "c1", bidder_id: "bidder-d", verdict: "NeedsManualReview", confidence: 0.58, explanation: "Force Motors submitted combined automotive turnover. Defence segment not separately reported. FY2024 had one large defence order that skews 3-year average. Manual verification needed.", evidence: [{ bidder_doc_id: "d6", page: 2, bbox: { page: 2, x0: 72, y0: 210, x1: 540, y1: 250 }, quote: "Total turnover FY22-24: INR 3,218 Cr (auto + defence combined). Segment split not provided.", score: 0.54 }] },
  { criterion_id: "c2", bidder_id: "bidder-d", verdict: "NeedsManualReview", confidence: 0.61, explanation: "ISO 9001:2015 certificate found but for Pune plant only. Defence vehicle manufacturing also occurs at Pithampur plant which is not covered.", evidence: [{ bidder_doc_id: "d6", page: 6, bbox: { page: 6, x0: 72, y0: 120, x1: 540, y1: 170 }, quote: "ISO 9001:2015 — TUV SUD — Scope: Pune Manufacturing Facility — Valid Jan 2026", score: 0.59 }] },
  { criterion_id: "c3", bidder_id: "bidder-d", verdict: "Eligible", confidence: 0.85, explanation: "Force Motors has 35+ years of vehicle manufacturing experience. Defence vehicle supply to BSF documented.", evidence: [{ bidder_doc_id: "d6", page: 3, bbox: { page: 3, x0: 72, y0: 100, x1: 540, y1: 140 }, quote: "Force Motors Ltd established 1958. Defence segment: BSF supply contract 2018-2022.", score: 0.84 }] },
  { criterion_id: "c4", bidder_id: "bidder-d", verdict: "NeedsManualReview", confidence: 0.55, explanation: "Non-blacklisting declaration submitted but dated 14 months ago. A fresh declaration (within 6 months) may be required per tender clause 8.3.", evidence: [{ bidder_doc_id: "d6", page: 8, bbox: { page: 8, x0: 72, y0: 390, x1: 540, y1: 420 }, quote: "Self-declaration dated: 12 February 2023 — blacklisting status as on that date.", score: 0.51 }] },
  { criterion_id: "c5", bidder_id: "bidder-d", verdict: "NotEligible", confidence: 0.84, explanation: "Net worth of INR 1.8 Cr as reported falls below the INR 2 Cr requirement. No CA certificate provided to challenge this figure.", evidence: [{ bidder_doc_id: "d6", page: 4, bbox: { page: 4, x0: 72, y0: 300, x1: 540, y1: 330 }, quote: "Net worth as on 31.03.2024: INR 1,82,34,567 (Rupees One Crore Eighty Two Lakhs)", score: 0.83 }] },
  { criterion_id: "c6", bidder_id: "bidder-d", verdict: "NotEligible", confidence: 0.87, explanation: "No Class III DSC certificate found in submission. Only a Class II certificate was provided, which is insufficient per clause 6.2.", evidence: [{ bidder_doc_id: "d6", page: 1, bbox: { page: 1, x0: 72, y0: 60, x1: 400, y1: 90 }, quote: "DSC Class II — e-Mudhra — Force Motors Ltd — Valid 2025", score: 0.85 }] },
];

export const MOCK_MATRIX: EvaluationMatrix = {
  tender_id: "crpf-1",
  bidders: MOCK_BIDDERS,
  criteria: MOCK_CRITERIA,
  verdicts: MOCK_VERDICTS,
};
