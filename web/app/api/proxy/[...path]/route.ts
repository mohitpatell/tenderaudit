import { type NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL || "http://localhost:8001";

async function proxyRequest(req: NextRequest, params: { path: string[] }) {
  const { path } = params;
  const targetPath = path.join("/");
  const targetUrl = `${API_URL}/${targetPath}${req.nextUrl.search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    // Skip headers that shouldn't be forwarded
    if (!["host", "connection", "transfer-encoding"].includes(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  const body = req.method !== "GET" && req.method !== "HEAD" ? await req.arrayBuffer() : undefined;

  try {
    const upstreamRes = await fetch(targetUrl, {
      method: req.method,
      headers,
      body: body ? Buffer.from(body) : undefined,
      // @ts-expect-error Node fetch supports duplex
      duplex: "half",
    });

    const resHeaders = new Headers();
    upstreamRes.headers.forEach((value, key) => {
      if (!["connection", "transfer-encoding"].includes(key.toLowerCase())) {
        resHeaders.set(key, value);
      }
    });

    return new NextResponse(upstreamRes.body, {
      status: upstreamRes.status,
      headers: resHeaders,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Upstream unreachable";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, await params);
}
export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, await params);
}
export async function PUT(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, await params);
}
export async function PATCH(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, await params);
}
export async function DELETE(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, await params);
}
