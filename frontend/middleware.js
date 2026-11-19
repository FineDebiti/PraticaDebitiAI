import { NextResponse } from "next/server";

const EMBED_CSP =
  "frame-ancestors 'self' https://flow-canvas-automations.lovable.app https://id-preview--49092334-bbfd-47c6-9334-7ba579814b60.lovable.app https://lovable.dev";
const BACKEND_INTERNAL_URL = (process.env.BACKEND_INTERNAL_URL || "http://backend:8000").replace(/\/+$/, "");

const LOCAL_LAN_REGEX = /^(?:192\.168\.1\.\d{1,3}|100\.80\.46\.\d{1,3})$/;
const SAFE_HOST_REGEX = /^[a-zA-Z0-9.\-:]+$/;
const SAFE_PATH_REGEX = /^\/(?!\/)/;

let cachedHmacSecret = "";
let cachedHmacKey = null;

function b64UrlToUint8Array(str) {
  const b64 = str.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (str.length % 4)) % 4);
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) {
    out[i] = bin.charCodeAt(i);
  }
  return out;
}

async function getHmacVerifyKey(secret) {
  if (cachedHmacKey && cachedHmacSecret === secret) {
    return cachedHmacKey;
  }
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"]
  );
  cachedHmacSecret = secret;
  cachedHmacKey = key;
  return key;
}

async function verifySignedSession(token, requiredScope, secret) {
  if (!token || !secret || !token.includes(".")) return false;
  const dotIdx = token.indexOf(".");
  const payloadB64 = token.slice(0, dotIdx);
  const sigB64 = token.slice(dotIdx + 1);
  if (!payloadB64 || !sigB64) return false;
  try {
    const key = await getHmacVerifyKey(secret);
    const sigBytes = b64UrlToUint8Array(sigB64);
    const validSig = await crypto.subtle.verify(
      "HMAC",
      key,
      sigBytes,
      new TextEncoder().encode(payloadB64)
    );
    if (!validSig) return false;

    const payloadJson = new TextDecoder().decode(b64UrlToUint8Array(payloadB64));
    const payload = JSON.parse(payloadJson);
    if (payload.scope !== requiredScope) return false;
    if (Number(payload.exp || 0) <= Math.floor(Date.now() / 1000)) return false;
    return true;
  } catch {
    return false;
  }
}

async function redeemTicket(ticket, scope, serverSecret) {
  if (!ticket || !serverSecret) return { ok: false };
  try {
    const res = await fetch(`${BACKEND_INTERNAL_URL}/api/auth/redeem`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${serverSecret}`,
      },
      body: JSON.stringify({ ticket, scope }),
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return { ok: false };
    const body = await res.json();
    if (!body?.ok || !body?.session_token) return { ok: false };
    return { ok: true, sessionToken: body.session_token };
  } catch {
    return { ok: false };
  }
}

function getClientHost(request) {
  const raw =
    request.headers.get("x-forwarded-host") ||
    request.headers.get("host") ||
    request.nextUrl.hostname ||
    "";
  return raw.split(",")[0].trim().replace(/^\[|\]$/g, "").split(":")[0].toLowerCase();
}

function getPublicOrigin(request) {
  const fwdProto = (request.headers.get("x-forwarded-proto") || "").split(",")[0].trim().toLowerCase();
  const proto = fwdProto === "https" || fwdProto === "http" ? fwdProto : request.nextUrl.protocol.replace(":", "").toLowerCase() || "http";
  const candidateHost = (request.headers.get("x-forwarded-host") || request.headers.get("host") || "")
    .split(",")[0]
    .trim();
  const safeHost = SAFE_HOST_REGEX.test(candidateHost) ? candidateHost : (request.nextUrl.host || "localhost:3001");
  return `${proto}://${safeHost}`;
}

function isLocalHostname(host) {
  return (
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "::1" ||
    LOCAL_LAN_REGEX.test(host)
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
    return applySecurityHeaders(NextResponse.json({ detail: message }, { status }));
  }
  const html = `<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Accesso Riservato - DossierLex</title></head><body style="font-family:system-ui,sans-serif;background:#f7f5f0;color:#1e261f;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0"><div style="background:#fff;border:1px solid #d9d4c7;border-radius:10px;padding:28px 32px;max-width:480px;box-shadow:0 8px 24px rgba(0,0,0,0.06)"><h1 style="margin:0 0 8px;font-size:20px">${status} — Accesso riservato</h1><p style="margin:0;color:#555;font-size:14px">${message}</p></div></body></html>`;
  return applySecurityHeaders(
    new NextResponse(html, {
      status,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    })
  );
}

export async function middleware(request) {
  const rawPathname = request.nextUrl.pathname || "/";
  const pathname = SAFE_PATH_REGEX.test(rawPathname) ? rawPathname : "/";
  const isEmbedRoute = pathname === "/embed" || pathname.startsWith("/embed/");
  const isEmbedApi = pathname === "/api/embed" || pathname.startsWith("/api/embed/");
  const isApi = pathname.startsWith("/api/");
  const externalHttps = isExternalHttpsRequest(request);
  const serverSecret = (process.env.DOSSIERLEX_SERVER_SECRET || "").trim();

  // Endpoint server-to-server per emissione ticket (verifica Bearer affidata al backend FastAPI)
  if (pathname === "/api/auth/ticket") {
    if (!["POST", "OPTIONS"].includes(request.method)) {
      return applySecurityHeaders(NextResponse.json({ detail: "Method not allowed" }, { status: 405 }));
    }
    return applySecurityHeaders(NextResponse.next());
  }

  // Blocca chiamate esterne dirette all'endpoint interno di riscatto ticket
  if (pathname === "/api/auth/redeem") {
    return unauthorizedResponse(true, "Endpoint interno non esposto.", 403);
  }

  // 1. Protezione /embed e /api/embed/* (solo ticket monouso scope="embed" + cookie SameSite=None; Secure)
  if (isEmbedRoute || isEmbedApi) {
    if (isEmbedApi && !["GET", "HEAD", "OPTIONS"].includes(request.method)) {
      return applySecurityHeaders(
        NextResponse.json({ detail: "Endpoint /api/embed in sola lettura." }, { status: 405 })
      );
    }

    const qTicket = (request.nextUrl.searchParams.get("ticket") || "").trim();
    const sessionCookie = (request.cookies.get("dossierlex_embed_session")?.value || "").trim();

    if (qTicket && !isApi) {
      if (!serverSecret) {
        return unauthorizedResponse(false, "DOSSIERLEX_SERVER_SECRET non configurato.", 403);
      }
      const redeemed = await redeemTicket(qTicket, "embed", serverSecret);
      if (!redeemed.ok) {
        return unauthorizedResponse(false, "Ticket /embed non valido, scaduto o già utilizzato.", 401);
      }
      const response = applySecurityHeaders(NextResponse.next());
      response.cookies.set("dossierlex_embed_session", redeemed.sessionToken, {
        httpOnly: true,
        secure: externalHttps,
        sameSite: externalHttps ? "none" : "lax",
        path: "/",
        maxAge: 28800,
      });
      return response;
    }

    if (externalHttps) {
      if (!serverSecret) {
        return unauthorizedResponse(isApi, "DOSSIERLEX_SERVER_SECRET non configurato sul server.", 403);
      }
      const okSession = await verifySignedSession(sessionCookie, "embed", serverSecret);
      if (!okSession) {
        return unauthorizedResponse(isApi, "Ticket monouso o sessione /embed mancante o scaduta.", 401);
      }
    }

    return applySecurityHeaders(NextResponse.next());
  }

  // 2. Gestione ?ticket= (scope="full") solo su rotte pagina GET/HEAD con redirect pulito a /
  const qFullTicket = (request.nextUrl.searchParams.get("ticket") || "").trim();
  if (qFullTicket && !isApi && (request.method === "GET" || request.method === "HEAD")) {
    if (!serverSecret) {
      return unauthorizedResponse(false, "DOSSIERLEX_SERVER_SECRET non configurato.", 403);
    }
    const redeemed = await redeemTicket(qFullTicket, "full", serverSecret);
    if (!redeemed.ok) {
      return unauthorizedResponse(false, "Ticket di accesso non valido, scaduto o già utilizzato.", 401);
    }
    const cleanSearch = new URLSearchParams(request.nextUrl.searchParams);
    cleanSearch.delete("ticket");
    const qs = cleanSearch.toString();
    const targetUrl = `${getPublicOrigin(request)}${pathname}${qs ? `?${qs}` : ""}`;
    const response = applySecurityHeaders(NextResponse.redirect(targetUrl, 302));
    response.cookies.set("dossierlex_admin_session", redeemed.sessionToken, {
      httpOnly: true,
      secure: externalHttps,
      sameSite: "lax",
      path: "/",
      maxAge: 28800,
    });
    return response;
  }

  // 3. Tutte le altre rotte (/ e /api/*) su HTTPS esterno richiedono sessione "full"
  if (externalHttps) {
    if (!serverSecret) {
      return unauthorizedResponse(isApi, "Accesso HTTPS bloccato: DOSSIERLEX_SERVER_SECRET non configurato.", 403);
    }
    const adminCookie = (request.cookies.get("dossierlex_admin_session")?.value || "").trim();
    const okAdmin = await verifySignedSession(adminCookie, "full", serverSecret);
    if (!okAdmin) {
      return unauthorizedResponse(isApi, "Accesso HTTPS riservato: ticket monouso richiesto.", 401);
    }
    return applySecurityHeaders(NextResponse.next());
  }

  // 4. Rete locale diretta (localhost, 192.168.1.*, 100.80.46.*): accesso libero
  return applySecurityHeaders(NextResponse.next());
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico|DossierLex-logo\\.svg|DossierLex-logo-white\\.svg).*)"],
};
