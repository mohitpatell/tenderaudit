# TenderAudit — Web

Next.js 15 (App Router) frontend for TenderAudit.

## Run

```bash
npm install
npm run dev      # http://localhost:3001
```

Backend FastAPI must be running on port 8001 (see project root `make dev`).

## Routes

| Route | Purpose |
|---|---|
| `/` | Landing — upload tender PDF |
| `/tender/[id]/criteria` | Review and approve extracted eligibility criteria |
| `/tender/[id]/upload-bidders` | Upload bidder document bundles |
| `/tender/[id]/matrix` | **Hero** — bidder × criterion evaluation matrix |
| `/bidder/[bidId]/criterion/[critId]` | Evidence drill-down (page, bbox, quote) |

## Architecture

- **App Router** server components for data fetching, client components for matrix and drill-down.
- **API proxy** at `/api/proxy/[...path]` forwards every method to the FastAPI backend on `:8001`.
- **PDF rendering** via `@react-pdf-viewer/core` for the source-citation overlay in the drill-down screen.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `API_URL` | `http://localhost:8001` | FastAPI backend URL |
