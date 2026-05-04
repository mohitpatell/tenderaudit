# TenderAudit — Air-Gap Deployment Guide

This document describes how to run TenderAudit with no internet egress (Level 1) and on local sovereign GPU infrastructure (Level 2). The CRPF procurement use case makes air-gap a hard requirement, not an option.

---

## Why Air-Gap Matters for Procurement

CRPF procurement evaluation happens within a Tier-3 datacentre at HQ Delhi (CGO Complex). The bidder documents being evaluated — CA turnover certificates, audited balance sheets, OEM authorization letters — are commercially sensitive and in some cases contain classified vendor relationships. They must not transit a public network or be processed by a foreign cloud service.

CRPF's network reality per the source spec: "HQ Delhi GPUs only, edge sites CPU-only." Level 2 applies to HQ Delhi; Level 1 applies to all CRPF formations outside Delhi.

---

## Level 1: No Internet Egress

### What works in Level 1

- Tender PDF ingest (PyMuPDF + PaddleOCR-VL)
- Bidder document ingest and chunking
- Embedding-free retrieval: BM25 keyword search over bidder chunks (fallback when no vector DB)
- Officer reviews extracted criteria manually (LLM extraction skipped)
- Officer reviews bidder documents manually and records verdicts
- No-silent-disqualification guard still enforced on manually entered verdicts
- pyHanko signing of the matrix PDF (self-signed cert; no OCSP call needed offline)
- SHA-256 hash-chained audit log

### What is skipped in Level 1

- LLM criterion extraction (officer enters criteria manually)
- LLM per-(criterion, bidder) evaluation (officer records verdict manually)
- Vector embedding of bidder chunks (BM25 fallback only)

### Environment setup

```bash
LLM_BACKEND=none
EMBEDDING_BACKEND=bm25   # keyword search fallback
OPENAI_API_KEY=
VLLM_BASE_URL=
```

### Container requirements

| Dependency | Size |
|---|---|
| PyMuPDF 1.24 | ~8 MB |
| PaddleOCR-VL 1.5 | ~900 MB |
| LayoutLMv3-base (for chunk classification) | ~450 MB |
| BM25 (rank_bm25) | ~1 MB |
| pyHanko + cryptography | ~25 MB |
| PostgreSQL client + psycopg2 | ~30 MB |
| All Python venv deps | ~600 MB |
| Node 20 + Next.js static build | ~200 MB |

Total image (Level 1): ~2.3 GB compressed.

### Supported host OS

- RHEL 8 / RHEL 9 (primary — CRPF HQ Delhi, Karnataka SDC)
- Ubuntu 22.04 LTS
- Any Linux with Docker 24+ or Podman 4+

```bash
docker load -i tenderaudit-airgap-level1.tar.gz
docker run -d \
  --name tenderaudit \
  -p 8001:8001 -p 3001:3001 \
  -v /data/tenderaudit:/data/db \
  -e LLM_BACKEND=none \
  -e EMBEDDING_BACKEND=bm25 \
  tenderaudit:level1
```

---

## Level 2: Sovereign GPU (vLLM)

Level 2 enables full LLM extraction and evaluation using a locally served open-weights model. This is the target for CRPF HQ Delhi and state procurement cells with GPU access.

### Hardware envelope

| VRAM | GPU example | Recommended model | VRAM usage |
|---|---|---|---|
| 24 GB | NVIDIA L4 or A30 | Qwen 3 14B (Q4_K_M) | ~14 GB |
| 40 GB | NVIDIA A100 40GB | Qwen 2.5 32B (Q4_K_M) | ~22 GB |
| 40 GB | NVIDIA A100 40GB | Gemma 3 27B (Q4_K_M) | ~22.5 GB |
| 80 GB | NVIDIA H100 80GB | Llama 3.3 70B (Q4_K_M) | ~48 GB |

For TenderAudit specifically, Qwen 2.5 32B Q4 on a single A100 40GB is the recommended production target. The GAVEL benchmark shows Qwen 3 in an agentic checklist scaffold is within 7% of GPT-4.1 at 36% fewer tokens — acceptable for structured procurement evaluation.

For the embedding model in Level 2, replace `text-embedding-3-large` with `BAAI/bge-m3`:
- BGE-M3 leads Indian-language reverse retrieval: 32.1% R@1 across 12 Indian languages per arXiv:2601.10205
- Supports dense + sparse + multi-vector retrieval simultaneously
- 8,192-token context; 100+ languages including Hindi, Kannada, English
- Runs on CPU for embedding (GPU dedicated to LLM inference)

### vLLM serving recipe

```bash
# Qwen 2.5 32B Q4 on A100 40GB (recommended for CRPF HQ)
docker run -d \
  --gpus all \
  --name vllm-qwen32b \
  -p 8004:8004 \
  -v /models/qwen2.5-32b-instruct-q4:/model \
  vllm/vllm-openai:latest \
  --model /model \
  --dtype auto \
  --max-model-len 8192 \
  --structured-outputs-config '{"backend": "xgrammar"}' \
  --port 8004

# BGE-M3 embedding server (CPU-based; runs alongside vLLM)
docker run -d \
  --name embedding-bge-m3 \
  -p 8005:8005 \
  -v /models/bge-m3:/model \
  huggingface/text-embeddings-inference:latest \
  --model-id /model \
  --port 8005
```

### TenderAudit configuration for Level 2

```bash
# .env additions for Level 2
LLM_BACKEND=vllm
VLLM_BASE_URL=http://localhost:8004/v1
VLLM_MODEL_NAME=qwen2.5-32b
EMBEDDING_BACKEND=bge-m3
BGE_M3_BASE_URL=http://localhost:8005
```

The `LLMClient` calls the vLLM OpenAI-compatible endpoint with `guided_json` for structured outputs:

```python
client = openai.OpenAI(base_url=os.environ["VLLM_BASE_URL"], api_key="none")
response = client.beta.chat.completions.parse(
    model=os.environ["VLLM_MODEL_NAME"],
    messages=[system_prompt, user_content],
    response_format=Verdict,
    extra_body={"guided_json": Verdict.model_json_schema()}
)
```

---

## Migration Checklist (Prototype → Pilot Deployment)

### Step 1: Replace embeddings model

```bash
# Download before entering air-gap environment
pip install sentence-transformers
python -c "
from sentence_transformers import SentenceTransformer
SentenceTransformer('BAAI/bge-m3')
print('BGE-M3 downloaded')
"
# Transfer weights to air-gapped server via approved media
```

Set `EMBEDDING_BACKEND=bge-m3` in `.env`. Re-index all existing bidder chunks after switching (embeddings are not cross-model compatible).

### Step 2: Document the model card

For MeitY/STQC/CRPF security audit:

| Field | Value |
|---|---|
| Primary LLM | Qwen 2.5 32B Instruct (Q4_K_M) or Llama 3.3 70B (Q4_K_M) |
| Training data | Public internet (Alibaba/Meta open-weights; no CRPF or GoI data used in training) |
| Quantization | Q4_K_M via llama.cpp / GGUF |
| Serving framework | vLLM with xgrammar structured outputs |
| Evaluation corpus | 8 CRPF/GeM tender PDFs + 32 synthetic bidder bundles (see seed/) |
| Known failure modes | Handwritten signatures, scanned-and-rotated PDFs, Hindi-only documents without Latin numerals |
| Embedding model | BAAI/bge-m3; no external API calls |

### Step 3: Configure CSP-empanelled storage (cloud variant)

If not fully on-prem:

- Use MeitY MeghRaj-empanelled CSP: AWS Mumbai, Azure India, GCP Mumbai, Yotta Shakti, E2E Networks
- ISO 27001:2017 + ISO 27017:2015 + ISO 27018:2019 + ISO 20000-1:2018 compliance required from CSP
- Configure MinIO with S3-compatible endpoint of empanelled CSP
- Enable SSE-KMS; keys managed within India
- Data localization: all objects stored in India region

### Step 4: Replace self-signed certificate with NIC Class III DSC

The pyHanko signing in `sign_pdf.py` uses a self-signed certificate in the demo. For production:

```python
# sign_pdf.py — production configuration
signer = SimpleSigner.load(
    key_file="/etc/tenderaudit/nic-class3.key",   # NIC-issued private key
    cert_file="/etc/tenderaudit/nic-class3.pem",  # NIC-issued certificate
    ca_chain_files=[
        "/etc/tenderaudit/nic-sub-ca.pem",
        "/etc/tenderaudit/nic-root-ca.pem"
    ]
)
```

NIC issues Class III DSC through accredited Certifying Authorities under IT Act 2000 §24.

For multi-year audit defensibility: enable pyHanko Long-Term Validation (LTV) with OCSP stapling. In air-gap, pre-fetch OCSP responses and embed them at signing time.

### Step 5: STQC audit preparation

Required before `*.gov.in` or NIC-hosted deployment:

- VAPT by CERT-In empanelled auditor (web app, API, infrastructure, source code)
- Budget: ~₹3–8 lakh; timeline: 4–6 weeks
- CERT-In incident reporting: within 6 hours of detection (April 2022 directive)
- Accessibility audit: WCAG 2.1 AA via axe-core automated scan + manual check
- IS 17802 mapping document (GIGW 3.0 requirement)

---

## Indian Government AI Air-Gap Precedents

### BHASHINI → Yotta Shakti (2026)

MeitY's BHASHINI language AI platform migrated from a global hyperscaler to **Yotta Shakti Cloud (NVIDIA H100)** in early 2026, validated at Maha Kumbh 2025. This is the canonical precedent: a production Indian government AI workload runs entirely on a sovereign, MeitY-empanelled GPU cloud with no dependence on foreign infrastructure.

**Why it matters for TenderAudit:** if BHASHINI can serve millions of translation requests on sovereign infrastructure, TenderAudit can evaluate 50 procurement tenders per month on the same infrastructure.

### VoicERA (Feb 2026, MeitY)

Open-source voice AI on BHASHINI. Described by MeitY as "open, modular, interoperable, cloud-deployable, and ready for on-premise use." Establishes the pattern: open-weights + open-source serving framework + on-premise deployment is the preferred MeitY architecture for sensitive government AI.

### Shunya Labs Vāķ (Nasscom, 2026)

55-language voice AI built for "secure, privacy-first deployments across cloud, edge, and air-gapped systems." A private sector product already positioned for Indian government air-gap procurement — establishes commercial feasibility.

### Current AI + Bhashini Handheld Device (2026)

Fully offline 22-Indic-language AI running on an edge device. Demonstrates that even constrained hardware can run locally-sufficient inference. TenderAudit's Level 1 mode (BM25 + manual officer review) has lower compute requirements than this device.

### CDAC, NIC, NIELIT

All three run on-prem AI workloads. CDAC's PARAM supercomputers are the standard fine-tuning venue for Indian government AI. A future Qwen 2.5 32B fine-tune on CRPF procurement data could be submitted to CDAC for compute allocation under the NIC–CDAC MOU.

---

## Network Requirements by Mode

| Mode | Outbound internet | LLM service | Embedding service | Signing |
|---|---|---|---|---|
| Level 1 (manual) | None | None | BM25 (local) | pyHanko (self-signed, offline) |
| Level 2 (sovereign GPU) | None | localhost:8004 (vLLM) | localhost:8005 (BGE-M3) | pyHanko + pre-fetched OCSP |
| Prototype (OpenAI) | api.openai.com:443 | OpenAI API | OpenAI API | pyHanko (self-signed) |

---

## Air-Gap Mode UI Indicators

### Level 1 banner

A persistent full-width banner on every page:

> "Manual Evaluation Mode — LLM extraction and RAG disabled. All criteria and verdicts must be entered by the procuring officer."

The signed audit PDF watermark in Level 1:

> "Evaluated manually — no AI-assisted extraction. Officer: \<name\>. Date: \<ISO8601\>."

### Level 2 banner

A persistent footer:

> "AI: Qwen 2.5 32B Q4 @ localhost:8004 | Embeddings: BGE-M3 @ localhost:8005 | No internet egress"

The audit log records for every verdict:

```json
{
  "extraction_mode": "vllm",
  "llm_model": "qwen2.5-32b",
  "embedding_model": "bge-m3",
  "internet_egress": false
}
```
