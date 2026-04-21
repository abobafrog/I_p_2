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
  Progress,
  ProgressListResponse,
  PromoRedeemPayload,
  PromoRedeemResponse,
  RouteListResponse,
  SelectLevelPayload,
  SessionResponse,
  ShopResponse,
  SubmitAnswerPayload,
  TopicPayload,
  User,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

let csrfToken: string | null = null;

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

function buildHeaders(init?: RequestInit) {
  const headers = new Headers(init?.headers);
  const method = (init?.method || "GET").toUpperCase();
  const hasJsonBody = typeof init?.body === "string" && !headers.has("Content-Type");

  if (hasJsonBody) {
    headers.set("Content-Type", "application/json");
  }

  if (UNSAFE_METHODS.has(method) && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }

  return headers;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: buildHeaders(init),
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

export function applySession(session: SessionResponse | AuthResponse) {
  csrfToken = session.csrf_token;
}

export function clearSessionContext() {
  csrfToken = null;
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

export function getSession() {
  return request<SessionResponse>("/auth/session");
}

export function getMe() {
  return request<User>("/auth/me");
}

export function updateProfile(payload: AccountUpdatePayload) {
  return request<User>("/auth/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function logout() {
  return request<void>("/auth/logout", { method: "POST" });
}

export function getRoutes() {
  return request<RouteListResponse>("/game/routes");
}

export function getAllProgress() {
  return request<ProgressListResponse>("/game/progress");
}

export function getBootstrap(topic: string) {
  return request<BootstrapResponse>(`/game/bootstrap?topic=${encodeURIComponent(topic)}`);
}

export function resetProgress(topic: string) {
  return request<Progress>(`/game/reset?topic=${encodeURIComponent(topic)}`, {
    method: "POST",
  });
}

export function resetAllProgress() {
  return request<ProgressListResponse>("/game/reset-all", { method: "POST" });
}

export function selectLevel(payload: SelectLevelPayload) {
  return request<Progress>("/game/select-level", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function resetLevel(payload: TopicPayload) {
  return request<Progress>("/game/reset-level", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function submitAnswer(payload: SubmitAnswerPayload) {
  return request<AnswerResult>("/game/submit-answer", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getLeaderboard(topic: string, metric: LeaderboardMetric = "best_score") {
  return request<LeaderboardResponse>(
    `/leaderboard?topic=${encodeURIComponent(topic)}&metric=${encodeURIComponent(metric)}`,
  );
}

export function getShop() {
  return request<ShopResponse>("/shop");
}

export function buyOrEquipShopItem(itemId: string) {
  return request<ShopResponse>(`/shop/items/${encodeURIComponent(itemId)}`, {
    method: "POST",
  });
}

export function redeemPromoCode(payload: PromoRedeemPayload) {
  return request<PromoRedeemResponse>("/auth/redeem-promo", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAdminQuestions(topic: string) {
  return request<AdminQuestion[]>(`/admin/questions?topic=${encodeURIComponent(topic)}`);
}

export function createAdminQuestion(payload: AdminQuestionPayload) {
  return request<AdminQuestion>("/admin/questions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateAdminQuestion(questionId: number, payload: AdminQuestionPayload) {
  return request<AdminQuestion>(`/admin/questions/${questionId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteAdminQuestion(questionId: number) {
  return request<void>(`/admin/questions/${questionId}`, { method: "DELETE" });
}
