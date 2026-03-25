"use client";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("wasteiq_token");
}

export function setToken(token: string) {
  localStorage.setItem("wasteiq_token", token);
}

export function clearToken() {
  localStorage.removeItem("wasteiq_token");
}

export function isAuthenticated(): boolean {
  return !!getToken();
}
