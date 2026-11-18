import { NextResponse } from "next/server";

const EMBED_CSP =
  "frame-ancestors 'self' https://bentivegna-os.lovable.app https://preview--flow-canvas-automations.lovable.app";

function constantTimeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

function getClientHost(request) {
  const raw =
    request.headers.get("x-forwarded-host") ||
    request.headers.get("host") ||
    request.nextUrl.hostname ||
    "";
  return raw.split(",")[0].trim().replace(/^\[|\]$/g, "").split(":")[0].toLowerCase();
}

function isLocalHostname(host) {
  return (
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "::1" ||
    host.startsWith("192.168.1.") ||
    host.startsWith("100.80.46.")
  );
}

function isExternalHttpsRequest(request) {
  const fwdProto = (request.headers.get("x-forwarded-proto") || "").split(",")[0].trim().toLowerCase();
  const nextProto = request.nextUrl.protocol.replace(":", "").toLowerCase();
  const host = getClientHost(request);
  return fwdProto === "https" || nextProto === "https" || !isLocalHostname(host);
}

function applySecurityHeaders(response) {
  response.headers.set("Content-Security-Policy", EMBED_CSP);
  response.headers.delete("x-frame-options");
  response.headers.set("Cache-Control", "no-cache, no-store, must-revalidate");
  response.headers.set("Pragma", "no-cache");
  response.headers.set("Expires", "0");
  return response;
}

function unauthorizedResponse(isApi, message, status = 401) {
  if (isApi) {
    return applySecurityHeaders(
      NextResponse.json({ detail: message }, { status })
    );
  }
  const html = `<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Accesso Riservato - DossierLex</title></head><body style="font-family:system-ui,sans-serif;background:#f7f5f0;color:#1e261f;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0"><div style="background:#fff;border:1px solid #d9d4c7;border-radius:10px;padding:28px 32px;max-width:480px;box-shadow:0 8px 24px rgba(0,0,0,0.06)"><h1 style="margin:0 0 8px;font-size:20px">${status} — Accesso riservato</h1><p style="margin:0;color:#555;font-size:14px">${message}</p></div></body></html>`;
  return applySecurityHeaders(
    new NextResponse(html, {
      status,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    })
  );
}

export function middleware(request) {
  const pathname = request.nextUrl.pathname || "/";
  const isEmbedRoute = pathname === "/embed" || pathname.startsWith("/embed/");
  const isEmbedApi = pathname === "/api/embed" || pathname.startsWith("/api/embed/");
  const isApi = pathname.startsWith("/api/");
  const externalHttps = isExternalHttpsRequest(request);

  const embedExpected = (process.env.EMBED_READONLY_TOKEN || "").trim();
  const adminExpected = (process.env.ADMIN_TOKEN || "").trim();

  // 1. Protezione /embed e /api/embed/* (sola lettura tramite EMBED_READONLY_TOKEN)
  if (isEmbedRoute || isEmbedApi) {
    if (isEmbedApi && !["GET", "HEAD", "OPTIONS"].includes(request.method)) {
      return applySecurityHeaders(
        NextResponse.json({ detail: "Endpoint /api/embed in sola lettura." }, { status: 405 })
      );
    }

    const qToken = (request.nextUrl.searchParams.get("token") || "").trim();
    const hToken = (request.headers.get("x-embed-token") || "").trim();
    const cToken = (request.cookies.get("dossierlex_embed_token")?.value || "").trim();
    const suppliedEmbed = qToken || hToken || cToken;

    if (externalHttps && !embedExpected) {
      return unauthorizedResponse(isApi, "Token embed non configurato sul server.", 403);
    }
    if (embedExpected && !constantTimeEqual(suppliedEmbed, embedExpected)) {
      return unauthorizedResponse(isApi, "Token di sola lettura mancante o non valido.", 401);
    }

    const response = applySecurityHeaders(NextResponse.next());
    if (qToken && embedExpected && constantTimeEqual(qToken, embedExpected)) {
      const fwdProto = (request.headers.get("x-forwarded-proto") || "").toLowerCase();
      const useSecure = externalHttps || fwdProto === "https" || request.nextUrl.protocol === "https:";
      response.cookies.set("dossierlex_embed_token", qToken, {
        httpOnly: true,
        secure: useSecure,
        sameSite: useSecure ? "none" : "lax",
        path: "/",
      });
    }
    return response;
  }

  // 2. Protezione dell'intera app (/, /pratiche/*, /api/*) su richieste HTTPS esterne
  if (externalHttps) {
    if (!adminExpected) {
      return unauthorizedResponse(isApi, "Accesso HTTPS bloccato: ADMIN_TOKEN non configurato.", 403);
    }

    const qAdmin = (request.nextUrl.searchParams.get("access_token") || "").trim();
    const hAdmin = (request.headers.get("x-access-token") || "").trim();
    const authHdr = (request.headers.get("authorization") || "").trim();
    const bearerAdmin = authHdr.toLowerCase().startsWith("bearer ") ? authHdr.slice(7).trim() : "";
    const cAdmin = (request.cookies.get("dossierlex_admin_token")?.value || "").trim();
    const suppliedAdmin = qAdmin || hAdmin || bearerAdmin || cAdmin;

    if (!constantTimeEqual(suppliedAdmin, adminExpected)) {
      return unauthorizedResponse(
        isApi,
        "Accesso HTTPS riservato: fornire un access_token valido.",
        401
      );
    }

    const response = applySecurityHeaders(NextResponse.next());
    if (qAdmin && constantTimeEqual(qAdmin, adminExpected)) {
      response.cookies.set("dossierlex_admin_token", qAdmin, {
        httpOnly: true,
        secure: true,
        sameSite: "lax",
        path: "/",
      });
    }
    return response;
  }

  // 3. Accesso diretto da rete locale (localhost, 192.168.1.*, 100.80.46.*): libero
  return applySecurityHeaders(NextResponse.next());
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
