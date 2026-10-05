const TOKEN_KEY = "auth_token";

function isTokenExpired(token: string) {
  try {
    const payload = token.split(".")[1];
    if (!payload) return true;

    const decoded = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    return typeof decoded.exp !== "number" || decoded.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

function getCookieOptions() {
  const isSecureContext = typeof window !== "undefined" && window.location.protocol === "https:";

  return `${isSecureContext ? "; Secure" : ""}; SameSite=Lax; path=/; max-age=86400`;
}

export function setClientToken(token: string) {
  if (typeof window === "undefined") return;

  document.cookie = `${TOKEN_KEY}=${encodeURIComponent(token)}${getCookieOptions()}`;
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function getClientToken() {
  if (typeof window === "undefined") return null;

  const sessionToken = sessionStorage.getItem(TOKEN_KEY);
  if (sessionToken) {
    if (isTokenExpired(sessionToken)) {
      clearClientToken();
      return null;
    }
    return sessionToken;
  }

  const cookies = document.cookie.split(";");
  const tokenCookie = cookies.find((cookie) => cookie.trim().startsWith(`${TOKEN_KEY}=`));

  if (!tokenCookie) return null;

  const value = tokenCookie.split("=")[1];
  const token = decodeURIComponent(value);
  if (isTokenExpired(token)) {
    clearClientToken();
    return null;
  }
  return token;
}

export function clearClientToken() {
  if (typeof window === "undefined") return;

  document.cookie = `${TOKEN_KEY}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax${window.location.protocol === "https:" ? "; Secure" : ""}`;
  sessionStorage.removeItem(TOKEN_KEY);
}

export function getUserIdFromToken(token: string | null): number | null {
  if (!token) return null;

  try {
    const payload = token.split(".")[1];
    if (!payload) return null;

    const decoded = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    const userId = decoded?.sub;

    return userId ? Number(userId) : null;
  } catch {
    return null;
  }
}
