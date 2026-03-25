import { NextRequest, NextResponse } from "next/server";

const BACKEND = "https://wasteiq-rho.vercel.app";

async function handler(req: NextRequest, { params }: { params: { path: string[] } }) {
  const path = params.path.join("/");
  const search = req.nextUrl.search;
  const url = `${BACKEND}/${path}${search}`;

  const headers: Record<string, string> = {};
  const contentType = req.headers.get("content-type");
  if (contentType) headers["content-type"] = contentType;
  const auth = req.headers.get("authorization");
  if (auth) headers["authorization"] = auth;

  const body =
    req.method !== "GET" && req.method !== "HEAD" ? await req.text() : undefined;

  const res = await fetch(url, { method: req.method, headers, body });
  const data = await res.text();

  return new NextResponse(data, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") || "application/json" },
  });
}

export {
  handler as GET,
  handler as POST,
  handler as PUT,
  handler as DELETE,
  handler as PATCH,
};
