"""TenderAudit FastAPI app entry point.

Boot:

    cd tenderaudit && pip install -r api/requirements.txt && \
        uvicorn api.main:app --reload --port 8001

In-process state lives on ``app.state``:

- ``tenders``: ``dict[str, Tender]``
- ``bidders``: ``dict[tender_id, dict[bidder_id, Bidder]]``
- ``matrices``: ``dict[tender_id, EvaluationMatrix]``
- ``tender_blob``: ``dict[tender_id, blob_id]`` (original PDF)
- ``audit_conn``: persistent SQLite connection for the hash-chain audit log
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

# Load .env (project root) before importing modules that read os.getenv at import time.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .core import audit as audit_mod
from .core import persistence
from .core import storage
from .domain.routes import audit as audit_routes
from .domain.routes import bidders as bidders_routes
from .domain.routes import tenders as tenders_routes

log = logging.getLogger(__name__)

DEFAULT_AUDIT_DB = "./data/audit.db"


def _init_state(app: FastAPI) -> None:
    """Open the audit DB and rehydrate in-memory state from SQLite."""
    db_path = os.getenv("AUDIT_DB", DEFAULT_AUDIT_DB)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    audit_mod.init_db(conn)
    persistence.init_db(conn)
    app.state.audit_conn = conn

    tenders, bidders, matrices, tender_blob = persistence.load_state(conn)
    app.state.tenders = tenders
    app.state.bidders = bidders
    app.state.matrices = matrices
    app.state.tender_blob = tender_blob


def create_app() -> FastAPI:
    app = FastAPI(title="TenderAudit API", version="0.1.0")
    cors_env = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://localhost:3001",
    )
    allow_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def _startup() -> None:
        _init_state(app)

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        try:
            app.state.audit_conn.close()
        except Exception:  # pragma: no cover
            pass

    app.include_router(tenders_routes.router)
    app.include_router(bidders_routes.router)
    app.include_router(audit_routes.router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/files/{blob_id}")
    async def get_blob(blob_id: str) -> FileResponse:
        path = storage.get_path(blob_id)
        if path is None:
            raise HTTPException(status_code=404, detail="blob not found")
        meta = storage.get_meta(blob_id)
        return FileResponse(
            str(path),
            filename=meta.filename if meta else blob_id,
            media_type=(meta.content_type if meta and meta.content_type else "application/octet-stream"),
        )

    return app


app = create_app()
