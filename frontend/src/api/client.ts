/* Thin fetch wrappers around the Sada API (PRD section 6). Every call goes through
   request() so error handling and the friendly-message extraction live in
   one place. */
import type { Attempt, AttemptSummary, Passage, Reciter, User } from "./types";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function messageFromBody(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0] && typeof detail[0].msg === "string") {
      return detail[0].msg;
    }
  }
  if (status === 413) return "That recording is too large. Try a shorter take.";
  if (status >= 500) return "Something went wrong on our end. Please try again in a moment.";
  return "That didn't work. Please try again.";
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(path, { credentials: "same-origin", ...options });
  } catch {
    throw new ApiError("We couldn't reach the server. Check your connection and try again.", 0);
  }
  const isJson = (resp.headers.get("content-type") || "").includes("application/json");
  const body = isJson ? await resp.json().catch(() => null) : null;
  if (!resp.ok) throw new ApiError(messageFromBody(body, resp.status), resp.status, body);
  return body as T;
}

function jsonBody(obj: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(obj),
  };
}

export const api = {
  reciters: () => request<Reciter[]>("/api/reciters"),
  passage: (reciterId: number) =>
    request<Passage>(`/api/passages/fatiha?reciter_id=${encodeURIComponent(reciterId)}`),
  submitAttempt: (form: FormData) =>
    request<Attempt>("/api/attempts", { method: "POST", body: form }),
  attempt: (id: string) => request<Attempt>(`/api/attempts/${encodeURIComponent(id)}`),
  recentAttempts: () => request<AttemptSummary[]>("/api/attempts"),
  me: () => request<User | null>("/api/auth/me"),
  signup: (email: string, password: string) =>
    request<User>("/api/auth/signup", jsonBody({ email, password })),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", jsonBody({ email, password })),
  logout: () => request<null>("/api/auth/logout", { method: "POST" }),
};
