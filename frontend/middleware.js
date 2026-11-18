import { NextResponse } from "next/server";

const EMBED_CSP =
  "frame-ancestors 'self' https://bentivegna-os.lovable.app https://preview--flow-canvas-automations.lovable.app";

export function middleware(request) {
  const response = NextResponse.next();

  // Consente l'incorporamento iframe solo dai domini autorizzati di Bentivegna OS
  response.headers.set("Content-Security-Policy", EMBED_CSP);
  response.headers.delete("x-frame-options");

  // HTML e viste dinamiche sempre rivalidate ad ogni apertura iframe
  response.headers.set("Cache-Control", "no-cache, no-store, must-revalidate");
  response.headers.set("Pragma", "no-cache");
  response.headers.set("Expires", "0");

  // Se la rotta /embed riceve ?token= su HTTPS, imposta cookie compatibile cross-site iframe
  if (request.nextUrl.pathname.startsWith("/embed")) {
    const token = request.nextUrl.searchParams.get("token");
    const proto = request.headers.get("x-forwarded-proto") || request.nextUrl.protocol.replace(":", "");
    if (token && proto === "https") {
      response.cookies.set("dossierlex_embed_token", token, {
        httpOnly: true,
        secure: true,
        sameSite: "none",
        path: "/embed",
      });
    }
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
