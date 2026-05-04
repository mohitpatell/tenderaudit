# TenderAudit — Seed PDF Manifest

This file documents the 8 Government of India tender PDFs used for demo seeding and ground-truth evaluation.

## Expected Tender Files

| Filename | Source URL | Tender | Issuing Body |
|---|---|---|---|
| `crpf-1-gem-checklist.pdf` | https://crpf.gov.in/writereaddata/images/pdf/1035102020.pdf | CRPF GeM Procurement Checklist | CRPF |
| `crpf-2-bhopal-nit71.pdf` | https://crpf.gov.in/Upload/Tender/832082025-481.pdf | CRPF Bhopal Works NIT-71 | CRPF |
| `crpf-3-hyd-major-work.pdf` | https://crpf.gov.in/Upload/Tender/NIT026Part2-968.pdf | CRPF South Zone Hyderabad Major Works | CRPF |
| `crpf-4-jk-gc-snr.pdf` | https://crpf.gov.in/Upload/Tender/GCSNR-857.pdf | CRPF J&K GC Senior Works | CRPF |
| `mospi-5-it-infra.pdf` | https://mospi.gov.in/sites/default/files/tender_notification/Tender_IT_2015_16_16oct15.pdf | MoSPI / NSSTA IT Infrastructure | MoSPI |
| `mea-6-namibia-it.pdf` | https://www.mea.gov.in/Portal/Tender/1726_1/1_Final_Tender_Document.pdf | MEA Namibia IT Procurement | MEA |
| `stqc-7-iec-bis.pdf` | https://www.stqc.gov.in/sites/default/files/tenders/TenderDocumentForAnnualSubscriptionofIECBISStandards.pdf | STQC Annual Subscription IEC/BIS Standards | STQC |
| `cppp-8-model-tender.pdf` | https://eprocure.gov.in/cppp/sites/default/files/standard_biddingdocs/MTD%20Goods%20NIC.pdf | CPPP Model Tender Document (Goods) | CPPP/NIC |

## Manual Download Instructions

If `make seed` cannot reach the source URLs, download each PDF manually and drop it into `seed/pdfs/` using the **exact filename** listed above.

### Steps

1. Open each Source URL in a browser
2. Download the PDF
3. Rename it to the exact filename (e.g., `crpf-2-bhopal-nit71.pdf`)
4. Place it at `seed/pdfs/<filename>`
5. Verify: `ls -lh seed/pdfs/` — each file should be > 20 KB

### Placeholder Behaviour

If a real PDF cannot be fetched, `scripts/fetch_seed_pdfs.py` generates a reportlab placeholder containing:
- The tender title and issuing body
- Synthetic eligibility clauses matching the ground-truth criteria
- A visible `PLACEHOLDER` watermark

Bidder bundles (`scripts/gen_bidder_bundle.py`) work against either real or placeholder tenders.

## Bidder Bundles

After running `make seed`, synthetic bidder bundles are generated under `seed/bidders/`:

```
seed/bidders/
  {tender_stem}/
    bidder-a-clean/        # All docs valid; meets all criteria
    bidder-b-shortfall/    # Turnover ₹38L vs ₹41.6L threshold (FAIL C1)
    bidder-c-missing-iso/  # No ISO 9001 certificate (FAIL C5)
    bidder-d-ambiguous/    # ISO expired 2024; name on certs slightly differs (AMBIGUOUS)
```

Each bundle contains 12 PDFs — see `seed/bidders/{tender}/manifest.json` for doc metadata.

## Ground Truth

See `seed/ground_truth.json` for the machine-readable eligibility criteria used by tests and the compliance matrix demo.
