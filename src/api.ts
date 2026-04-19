import type {
  AdminQuestion,
  AdminQuestionPayload,
  AnswerResult,
  AuthResponse,
  BootstrapResponse,
  Credentials,
  LeaderboardResponse,
  Progress,
  SubmitAnswerPayload,
  User,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
const TOKEN_STORAGE_KEY = "froggy-coder-token";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function buildHeaders(token?: string, extra?: HeadersInit) {
  const headers = new Headers(extra);
  headers.set("Content-Type", "application/json");

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return headers;
}

async function request<T>(path: string, init?: RequestInit, token?: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: buildHeaders(token, init?.headers),
  });

  if (!response.ok) {
    let message = "Произошла ошибка запроса";

    try {
      const errorBody = (await response.json()) as { detail?: string };
      if (errorBody.detail) {
        message = errorBody.detail;
      }
    } catch {
      message = response.statusText || message;
    }

    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function loadStoredToken() {
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function persistToken(token: string) {
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken() {
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export function register(payload: Credentials) {
  return request<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function login(payload: Credentials) {
  return request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getMe(token: string) {
  return request<User>("/auth/me", undefined, token);
}

export function logout(token: string) {
  return request<void>("/auth/logout", { method: "POST" }, token);
}

export function getBootstrap(token: string, topic: string) {
  return request<BootstrapResponse>(
    `/game/bootstrap?topic=${encodeURIComponent(topic)}`,
    undefined,
    token,
  );
}

export function resetProgress(token: string, topic: string) {
  return request<Progress>(
    `/game/reset?topic=${encodeURIComponent(topic)}`,
    { method: "POST" },
    token,
  );
}

export function submitAnswer(token: string, payload: SubmitAnswerPayload) {
  return request<AnswerResult>(
    "/game/submit-answer",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function getLeaderboard(topic: string) {
  return request<LeaderboardResponse>(
    `/leaderboard?topic=${encodeURIComponent(topic)}`,
  );
}

export function getAdminQuestions(token: string, topic: string) {
  return request<AdminQuestion[]>(
    `/admin/questions?topic=${encodeURIComponent(topic)}`,
    undefined,
    token,
  );
}

export function createAdminQuestion(token: string, payload: AdminQuestionPayload) {
  return request<AdminQuestion>(
    "/admin/questions",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function updateAdminQuestion(
  token: string,
  questionId: number,
  payload: AdminQuestionPayload,
) {
  return request<AdminQuestion>(
    `/admin/questions/${questionId}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function deleteAdminQuestion(token: string, questionId: number) {
  return request<void>(
    `/admin/questions/${questionId}`,
    { method: "DELETE" },
    token,
  );
}
