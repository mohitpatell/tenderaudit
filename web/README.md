# TenderAudit — Web Frontend

Next.js 15 (App Router) frontend for the TenderAudit procurement evaluation system.

## Quick Start

```bash
npm install
npm run dev   # http://localhost:3001
```

Expects FastAPI backend on `http://localhost:8001`. Falls back to mock data (CRPF NIT-71) when backend is unavailable.

## Key Routes

| Route | Description |
|---|---|
| `/` | Landing — upload tender PDF or open a past tender |
| `/tender/[id]/criteria` | Review & approve extracted eligibility criteria |
| `/tender/[id]/upload-bidders` | Upload bidder ZIP archives |
| `/tender/[id]/matrix` | **HERO** — bidder × criterion evaluation matrix |
| `/bidder/[bidId]/criterion/[critId]` | Evidence drill-down with override |

## Environment

```
API_URL=http://localhost:8001   # FastAPI backend (default)
```

## Stack

- Next.js 15, React 19, TypeScript 5
- Tailwind CSS 3, shadcn/ui (slate/cyan theme)
- lucide-react, sonner, react-hook-form, zod
- react-resizable-panels (split pane)
