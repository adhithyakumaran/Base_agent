import { getInternalServiceToken as coreInternal } from "@/lib/api-auth-core";

export function getInternalServiceToken(): string | undefined {
  return coreInternal();
}

export function internalAgentHeaders(): Record<string, string> {
  const token = getInternalServiceToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export async function fetchInternalAgent(path: string, init?: RequestInit): Promise<Response> {
  const base = process.env.LOCAL_AGENT_URL || "http://127.0.0.1:43124";
  const headers = {
    ...(init?.headers || {}),
    ...internalAgentHeaders(),
  };
  return fetch(`${base}${path}`, { ...init, headers });
}
