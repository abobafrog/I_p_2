import type {
  AccountUpdatePayload,
  AdminQuestion,
  AdminQuestionPayload,
  AnswerResult,
  AuthResponse,
  BootstrapResponse,
  Credentials,
  LeaderboardMetric,
  LeaderboardResponse,
  ProgressListResponse,
  PromoRedeemPayload,
  PromoRedeemResponse,
  Progress,
  RouteListResponse,
  SelectLevelPayload,
  ShopResponse,
  SubmitAnswerPayload,
  TopicPayload,
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

function formatApiDetail(detail: unknown): string | null {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => formatApiDetail(item))
      .filter((item): item is string => Boolean(item));

    return messages.length > 0 ? messages.join(" | ") : null;
  }

  if (detail && typeof detail === "object") {
    const detailRecord = detail as {
      msg?: unknown;
      detail?: unknown;
      loc?: unknown;
    };

    if (typeof detailRecord.msg === "string") {
      const location = Array.isArray(detailRecord.loc)
        ? detailRecord.loc
            .slice(1)
            .map((item) => String(item))
            .join(".")
        : "";
      return location ? `${location}: ${detailRecord.msg}` : detailRecord.msg;
    }

    if ("detail" in detailRecord) {
      return formatApiDetail(detailRecord.detail);
    }

    try {
      return JSON.stringify(detail);
    } catch {
      return String(detail);
    }
  }

  return null;
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
      const errorBody = (await response.json()) as { detail?: unknown };
      const formattedDetail = formatApiDetail(errorBody.detail);
      if (formattedDetail) {
        message = formattedDetail;
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

export function updateProfile(token: string, payload: AccountUpdatePayload) {
  return request<User>(
    "/auth/profile",
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function logout(token: string) {
  return request<void>("/auth/logout", { method: "POST" }, token);
}

export function getRoutes(token: string) {
  return request<RouteListResponse>("/game/routes", undefined, token);
}

export function getAllProgress(token: string) {
  return request<ProgressListResponse>("/game/progress", undefined, token);
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

export function resetAllProgress(token: string) {
  return request<ProgressListResponse>(
    "/game/reset-all",
    { method: "POST" },
    token,
  );
}

export function selectLevel(token: string, payload: SelectLevelPayload) {
  return request<Progress>(
    "/game/select-level",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function resetLevel(token: string, payload: TopicPayload) {
  return request<Progress>(
    "/game/reset-level",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
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

export function getLeaderboard(topic: string, metric: LeaderboardMetric = "best_score") {
  return request<LeaderboardResponse>(
    `/leaderboard?topic=${encodeURIComponent(topic)}&metric=${encodeURIComponent(metric)}`,
  );
}

export function getShop(token: string) {
  return request<ShopResponse>("/shop", undefined, token);
}

export function buyOrEquipShopItem(token: string, itemId: string) {
  return request<ShopResponse>(
    `/shop/items/${encodeURIComponent(itemId)}`,
    { method: "POST" },
    token,
  );
}

export function redeemPromoCode(token: string, payload: PromoRedeemPayload) {
  return request<PromoRedeemResponse>(
    "/auth/redeem-promo",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
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
