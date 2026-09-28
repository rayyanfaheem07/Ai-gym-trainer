/**
 * Client-side token and authentication state helpers.
 * Never logs or exposes raw JWT secrets.
 */

const TOKEN_KEY = "ai_gym_access_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined" && typeof localStorage === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined" && typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch (err) {
    console.warn("Unable to save authentication token to localStorage:", err);
  }
}

export function removeStoredToken(): void {
  if (typeof window === "undefined" && typeof localStorage === "undefined") return;
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch (err) {
    console.warn("Unable to remove token from localStorage:", err);
  }
}

export function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return true;
    const payload = JSON.parse(atob(parts[1]));
    if (!payload.exp) return false;
    const nowSec = Math.floor(Date.now() / 1000);
    return payload.exp < nowSec;
  } catch {
    return true;
  }
}
