"use client";

import { signOut } from "next-auth/react";


let leavingProtectedApp = false;

export async function authenticatedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const response = await fetch(input, init);
  if (response.status === 401 && response.headers.get("X-Front-Desk-Auth-State") === "missing-session") leaveProtectedApp();
  return response;
}

function leaveProtectedApp() {
  if (leavingProtectedApp || typeof window === "undefined") return;
  leavingProtectedApp = true;
  void signOut({ redirect: false }).finally(() => window.location.replace("/sign-in"));
}
