"""PKCS#7 signed audit PDF generation.

Workflow:

1. Build a multi-page PDF from the EvaluationMatrix using reportlab
   (cover, criteria table, bidder bundle, matrix, evidence quotes,
   hash-chain footer).
2. If pyHanko + a self-signed cert are available, sign it in-place with
   PKCS#7. The cert is generated lazily on first use at
   ``./data/certs/tenderaudit-demo.p12``.

If signing dependencies are missing (or fail), the unsigned PDF is still
written and the function returns gracefully. The audit log records the
``signed: bool`` outcome.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .schemas import EvaluationMatrix

log = logging.getLogger(__name__)

CERT_DIR_DEFAULT = "./data/certs"
CERT_FILENAME = "tenderaudit-demo.p12"
CERT_PASSPHRASE = "tenderaudit-demo"


def sign_evaluation(
    matrix: EvaluationMatrix,
    output_path: str,
    *,
    chain_root: Optional[str] = None,
) -> dict:
    """Render and (best-effort) sign the audit PDF.

    Returns a dict ``{"path": str, "signed": bool, "reason": Optional[str]}``.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    _render_pdf(matrix, output_path, chain_root=chain_root)

    try:
        _sign_in_place(output_path)
        return {"path": output_path, "signed": True, "reason": None}
    except Exception as e:  # pragma: no cover - signing is best-effort
        log.warning("PDF signing skipped: %s", e)
        return {"path": output_path, "signed": False, "reason": str(e)}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_pdf(
    matrix: EvaluationMatrix,
    path: str,
    *,
    chain_root: Optional[str],
) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=A4, title="TenderAudit Audit Report")
    story: list = []

    story.append(Paragraph("TenderAudit Evaluation Report", styles["Title"]))
    story.append(Paragraph(f"Tender: {matrix.tender_id}", styles["Heading2"]))
    story.append(Spacer(1, 12))

    # Criteria table
    story.append(Paragraph("Criteria", styles["Heading2"]))
    crit_rows = [["ID", "Name", "Type", "Mandatory"]]
    for c in matrix.criteria:
        crit_rows.append([c.id, c.name, c.type, "Yes" if c.is_mandatory else "No"])
    story.append(_grid_table(crit_rows))
    story.append(Spacer(1, 12))

    # Bidder bundle
    story.append(Paragraph("Bidders", styles["Heading2"]))
    bidder_rows = [["ID", "Name", "Documents"]]
    for b in matrix.bidders:
        bidder_rows.append([b.id, b.name, str(len(b.documents))])
    story.append(_grid_table(bidder_rows))
    story.append(Spacer(1, 12))

    # Matrix
    story.append(Paragraph("Verdict Matrix", styles["Heading2"]))
    matrix_rows = [["Criterion", "Bidder", "Verdict", "Confidence"]]
    for v in matrix.verdicts:
        matrix_rows.append(
            [v.criterion_id, v.bidder_id, v.verdict, f"{v.confidence:.2f}"]
        )
    story.append(_grid_table(matrix_rows))
    story.append(Spacer(1, 12))

    # Evidence quotes
    story.append(Paragraph("Evidence", styles["Heading2"]))
    for v in matrix.verdicts:
        story.append(
            Paragraph(
                f"<b>{v.criterion_id} / {v.bidder_id}</b>: {v.verdict} ({v.confidence:.2f})",
                styles["BodyText"],
            )
        )
        story.append(Paragraph(v.explanation, styles["BodyText"]))
        for e in v.evidence:
            story.append(
                Paragraph(
                    f"&nbsp;&nbsp;[p{e.page}, doc {e.bidder_doc_id}] {e.quote[:300]}",
                    styles["BodyText"],
                )
            )
        story.append(Spacer(1, 6))

    # Hash chain footer
    story.append(Spacer(1, 12))
    story.append(Paragraph("Audit Chain", styles["Heading2"]))
    chain_summary = _audit_chain_summary(chain_root)
    story.append(Paragraph(chain_summary, styles["BodyText"]))

    doc.build(story)


def _grid_table(rows: list[list[str]]) -> Table:
    t = Table(rows, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return t


def _audit_chain_summary(chain_root: Optional[str]) -> str:
    """Return a short human-readable string describing the latest audit hash."""
    if not chain_root:
        return "Audit chain root not configured."
    db_path = Path(chain_root)
    if not db_path.exists():
        return f"Audit DB not found at {db_path}."
    try:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute(
                "SELECT id, this_hash FROM audit_log ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                return "Audit chain is empty."
            return f"Latest audit row: id={row[0]} hash={row[1]}"
        finally:
            conn.close()
    except Exception as e:  # pragma: no cover
        return f"Audit chain read failed: {e}"


# ---------------------------------------------------------------------------
# Signing (best-effort)
# ---------------------------------------------------------------------------


def _sign_in_place(path: str) -> None:
    """Sign ``path`` with the demo cert. Raises on missing pyHanko / cert."""
    try:
        from pyhanko.sign import signers
        from pyhanko.sign.signers.pdf_signer import PdfSigner, PdfSignatureMetadata
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    except ImportError as e:
        raise RuntimeError(f"pyHanko not installed: {e}") from e

    cert_path = _ensure_cert()
    signer = signers.SimpleSigner.load_pkcs12(
        pfx_file=str(cert_path),
        passphrase=CERT_PASSPHRASE.encode("utf-8"),
    )
    if signer is None:
        raise RuntimeError("Failed to load demo signing cert.")

    tmp_path = path + ".signed"
    with open(path, "rb") as inf, open(tmp_path, "wb") as outf:
        w = IncrementalPdfFileWriter(inf)
        meta = PdfSignatureMetadata(field_name="TenderAuditSignature")
        pdf_signer = PdfSigner(meta, signer=signer)
        pdf_signer.sign_pdf(w, output=outf)
    os.replace(tmp_path, path)


def _ensure_cert() -> Path:
    """Generate (if absent) a self-signed PKCS#12 demo cert; return its path."""
    cert_dir = Path(os.getenv("CERT_DIR", CERT_DIR_DEFAULT))
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / CERT_FILENAME
    if cert_path.exists():
        return cert_path

    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import pkcs12
        from cryptography.x509.oid import NameOID
        from datetime import datetime, timedelta, timezone
    except ImportError as e:
        raise RuntimeError(f"cryptography not installed: {e}") from e

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TenderAudit Demo"),
            x509.NameAttribute(NameOID.COMMON_NAME, "TenderAudit Demo CA"),
        ]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365 * 5))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=b"tenderaudit-demo",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(
            CERT_PASSPHRASE.encode("utf-8")
        ),
    )
    cert_path.write_bytes(p12_bytes)
    return cert_path
