import { useEffect, useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import bolotoBackdrop from "../boloto.png";
import swampBackdrop from "../swamp_bg.png";
import winBackdrop from "../win.jpg";
import {
  ApiError,
  applySession,
  buyOrEquipShopItem,
  clearSessionContext,
  createAdminQuestion,
  deleteAdminQuestion,
  getAllProgress,
  getAdminQuestions,
  getBootstrap,
  getLeaderboard,
  getRoutes,
  getSession,
  getShop,
  login,
  logout,
  redeemPromoCode,
  register,
  resetAllProgress,
  resetLevel,
  resetProgress,
  selectLevel,
  submitAnswer,
  updateProfile,
  updateAdminQuestion,
} from "./api";
import { FrogAvatar, FrogFamily, PrimitiveFrog } from "./components/FrogArt";
import { useRouteHearts } from "./hooks/useRouteHearts";
import type {
  AccountUpdatePayload,
  AdminQuestion,
  AdminQuestionPayload,
  AnswerResult,
  AuthResponse,
  Credentials,
  LeaderboardMetric,
  LeaderboardEntry,
  Progress,
  PromoRedeemPayload,
  Question,
  QuestionDraft,
  RouteOption,
  ShopItem,
  User,
} from "./types";

type View =
  | "auth"
  | "menu"
  | "difficulty"
  | "quiz"
  | "shop"
  | "account"
  | "leaderboard"
  | "admin"
  | "result";
type AuthMode = "login" | "register";
type FeedbackAction = "advance" | "retry" | "level-reset" | null;
type AccountFormState = {
  displayName: string;
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
};

type RoundResult = {
  finalScore: number;
  totalQuestions: number;
  bestScore: number;
  completedRuns: number;
  routeTitle: string;
};

const DEFAULT_TOPIC = "python-easy";
const HEARTS_PER_LEVEL = 3;
const APP_TITLE = "Froggy Coder";
const AUTH_SCENE_STYLE: CSSProperties = {
  backgroundImage: `linear-gradient(180deg, rgba(8, 18, 14, 0.18), rgba(8, 18, 14, 0.74)), url(${bolotoBackdrop})`,
};
const MENU_SCENE_STYLE: CSSProperties = {
  backgroundImage: `linear-gradient(180deg, rgba(8, 18, 14, 0.16), rgba(8, 18, 14, 0.76)), url(${swampBackdrop})`,
};
const RESULT_SCENE_STYLE: CSSProperties = {
  backgroundImage: `linear-gradient(180deg, rgba(8, 18, 14, 0.12), rgba(8, 18, 14, 0.68)), url(${winBackdrop})`,
};

function createEmptyDraft(topic = DEFAULT_TOPIC): QuestionDraft {
  return {
    topic,
    type: "choice",
    prompt: "",
    explanation: "",
    placeholder: "",
    order_index: "0",
    options_text: "Вариант 1\nВариант 2",
    answers_text: "Вариант 1",
  };
}

function createEmptyAccountForm(activeUser: User | null = null): AccountFormState {
  return {
    displayName: activeUser?.username ?? "",
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  };
}

function normalizeWhitespace(value: string) {
  return value.trim().replace(/\s+/g, " ");
}

function formatDate(value: string | null) {
  if (!value) {
    return "нет данных";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getRouteTitle(route: RouteOption | null) {
  if (!route) {
    return "Маршрут не выбран";
  }

  return `${route.language} • ${route.difficulty_label}`;
}

function getRouteTaskSummary(route: RouteOption) {
  return `${route.levels_total} уровней по ${route.tasks_per_level} задач`;
}

function getRouteContentHint(route: RouteOption) {
  return getRouteTaskSummary(route);
}

function getUserHandle(entity: Pick<User, "full_username" | "username" | "tag">) {
  return entity.full_username || (entity.tag ? `${entity.username}#${entity.tag}` : entity.username);
}

function getLeaderboardHandle(
  entry: Pick<LeaderboardEntry, "full_username" | "username" | "tag">,
) {
  return entry.full_username || (entry.tag ? `${entry.username}#${entry.tag}` : entry.username);
}

function getUniqueLanguages(routes: RouteOption[]) {
  return Array.from(new Set(routes.map((route) => route.language)));
}

function App() {
  const [view, setView] = useState<View>("auth");
  const [authMode, setAuthMode] = useState<AuthMode>("register");

  const [user, setUser] = useState<User | null>(null);
  const [routes, setRoutes] = useState<RouteOption[]>([]);
  const [currentRoute, setCurrentRoute] = useState<RouteOption | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState("Python");
  const [accountRouteTopic, setAccountRouteTopic] = useState<string | null>(null);

  const [questions, setQuestions] = useState<Question[]>([]);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [routeProgressCache, setRouteProgressCache] = useState<Record<string, Progress>>({});
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [leaderboardMetric, setLeaderboardMetric] =
    useState<LeaderboardMetric>("coins");
  const [leaderboardMetricLabel, setLeaderboardMetricLabel] =
    useState("Монеты");
  const [leaderboardScope, setLeaderboardScope] = useState<"route" | "global">("global");
  const [shopItems, setShopItems] = useState<ShopItem[]>([]);
  const [adminQuestions, setAdminQuestions] = useState<AdminQuestion[]>([]);
  const [selectedAdminQuestionId, setSelectedAdminQuestionId] = useState<number | null>(null);

  const [authForm, setAuthForm] = useState<Credentials>({
    username: "",
    password: "",
  });
  const [accountForm, setAccountForm] = useState<AccountFormState>(() =>
    createEmptyAccountForm(),
  );
  const [promoCode, setPromoCode] = useState("");

  const [selectedOption, setSelectedOption] = useState("");
  const [typedAnswer, setTypedAnswer] = useState("");
  const [feedback, setFeedback] = useState<AnswerResult | null>(null);
  const [feedbackAction, setFeedbackAction] = useState<FeedbackAction>(null);
  const [pendingProgress, setPendingProgress] = useState<Progress | null>(null);
  const [displayIndex, setDisplayIndex] = useState(0);
  const {
    hearts,
    setHearts,
    getStoredHearts,
    syncLevelHearts,
    clearRouteHearts,
    resetHeartsState,
  } = useRouteHearts(HEARTS_PER_LEVEL);
  const [showHint, setShowHint] = useState(false);
  const [roundResult, setRoundResult] = useState<RoundResult | null>(null);

  const [draft, setDraft] = useState<QuestionDraft>(() => createEmptyDraft());
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);

  const [busyLabel, setBusyLabel] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const languageOptions = getUniqueLanguages(routes);
  const difficultyOptions = routes.filter((route) => route.language === selectedLanguage);
  const currentQuestion = questions[displayIndex] ?? null;
  const selectedAdminQuestion =
    adminQuestions.find((question) => question.id === selectedAdminQuestionId) ??
    adminQuestions[0] ??
    null;
  const currentAnswer =
    currentQuestion?.type === "choice" ? selectedOption : typedAnswer;
  const canSubmitAnswer =
    currentQuestion !== null &&
    currentAnswer.trim().length > 0 &&
    feedback === null &&
    busyLabel.length === 0;

  useEffect(() => {
    void hydrateSession("menu", null, true);
  }, []);

  function rememberProgress(nextProgress: Progress) {
    setRouteProgressCache((prev) => ({
      ...prev,
      [nextProgress.topic]: nextProgress,
    }));
  }

  function replaceProgressCache(progressItems: Progress[]) {
    setRouteProgressCache(
      progressItems.reduce<Record<string, Progress>>((accumulator, item) => {
        accumulator[item.topic] = item;
        return accumulator;
      }, {}),
    );
  }

  function resetQuestionUi() {
    setSelectedOption("");
    setTypedAnswer("");
    setFeedback(null);
    setFeedbackAction(null);
    setPendingProgress(null);
  }

  function resetDraftForm(topic = currentRoute?.topic ?? routes[0]?.topic ?? DEFAULT_TOPIC) {
    setDraft(createEmptyDraft(topic));
    setEditingQuestionId(null);
  }

  function resetAccountForm(activeUser: User | null = user) {
    setAccountForm(createEmptyAccountForm(activeUser));
  }

  function storeSession(authResponse: AuthResponse) {
    applySession(authResponse);
    setUser(authResponse.user);
    resetAccountForm(authResponse.user);
  }

  function clearSession() {
    clearSessionContext();
    setUser(null);
    setRoutes([]);
    setCurrentRoute(null);
    setAccountRouteTopic(null);
    setQuestions([]);
    setProgress(null);
    setRouteProgressCache({});
    setLeaderboard([]);
    setLeaderboardMetric("coins");
    setLeaderboardMetricLabel("Монеты");
    setLeaderboardScope("global");
    setShopItems([]);
    setAdminQuestions([]);
    setRoundResult(null);
    resetHeartsState();
    setShowHint(false);
    resetQuestionUi();
    resetDraftForm(DEFAULT_TOPIC);
    resetAccountForm(null);
    setPromoCode("");
    setView("auth");
  }

  function handleApiFailure(error: unknown, forceLogout = false) {
    if (error instanceof ApiError) {
      setErrorMessage(error.message);
      if (forceLogout || error.status === 401) {
        clearSession();
      }
      return;
    }

    setErrorMessage("Произошла ошибка. Попробуйте еще раз.");
  }

  async function hydrateSession(
    nextView: View = "menu",
    sessionResponse: AuthResponse | null = null,
    silentAuthFailure = false,
  ) {
    setBusyLabel("Загружаем профиль...");
    setErrorMessage("");

    try {
      const activeSession = sessionResponse ?? (await getSession());
      storeSession(activeSession);

      const [routeResponse, progressResponse] = await Promise.all([
        getRoutes(),
        getAllProgress(),
      ]);

      setRoutes(routeResponse.items);
      replaceProgressCache(progressResponse.items);
      setAccountRouteTopic((prev) =>
        routeResponse.items.some((route) => route.topic === prev)
          ? prev
          : routeResponse.items[0]?.topic ?? null,
      );
      setSelectedLanguage(routeResponse.items[0]?.language ?? "Python");
      setDraft((prev) =>
        routeResponse.items.some((route) => route.topic === prev.topic)
          ? prev
          : createEmptyDraft(routeResponse.items[0]?.topic ?? DEFAULT_TOPIC),
      );
      setView(nextView);
    } catch (error) {
      if (silentAuthFailure && error instanceof ApiError && error.status === 401) {
        clearSession();
        setErrorMessage("");
        return;
      }

      handleApiFailure(error, true);
    } finally {
      setBusyLabel("");
    }
  }

  async function loadRoute(route: RouteOption, nextView: View = "difficulty") {
    if (!user) {
      return false;
    }

    setBusyLabel("Загружаем маршрут...");
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const [bootstrap, leaderboardResponse] = await Promise.all([
        getBootstrap(route.topic),
        getLeaderboard(route.topic, leaderboardMetric),
      ]);

      setCurrentRoute(route);
      setAccountRouteTopic(route.topic);
      setSelectedLanguage(route.language);
      setQuestions(bootstrap.questions);
      setProgress(bootstrap.progress);
      setUser(bootstrap.user);
      setLeaderboard(leaderboardResponse.entries);
      setLeaderboardMetric(leaderboardResponse.metric);
      setLeaderboardMetricLabel(leaderboardResponse.metric_label);
      setLeaderboardScope(leaderboardResponse.scope);
      setDisplayIndex(bootstrap.progress.current_index);
      syncLevelHearts(
        route.topic,
        bootstrap.progress.current_level_index,
        getStoredHearts(
          route.topic,
          bootstrap.progress.current_level_index,
          bootstrap.progress.remaining_hearts,
        ),
      );
      setShowHint(false);
      setRoundResult(null);
      rememberProgress(bootstrap.progress);
      resetQuestionUi();
      setView(nextView);
      return true;
    } catch (error) {
      handleApiFailure(error);
      return false;
    } finally {
      setBusyLabel("");
    }
  }

  async function handleAuthSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyLabel(authMode === "login" ? "Выполняем вход..." : "Создаем аккаунт...");
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const payload = {
        username: authForm.username.trim(),
        password: authForm.password,
      };

      const response =
        authMode === "login" ? await login(payload) : await register(payload);

      storeSession(response);
      setAuthForm({ username: "", password: "" });
      setSuccessMessage(
        authMode === "login"
          ? "Вход выполнен. Можно продолжать обучение."
          : `Аккаунт создан. Для входа используйте логин ${response.user.full_username}.`,
      );
      await hydrateSession("menu", response);
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function handleLogout() {
    if (!user) {
      clearSession();
      return;
    }

    setBusyLabel("Выходим...");
    setErrorMessage("");

    try {
      await logout();
    } catch {
      // Игнорируем сетевые ошибки logout и все равно чистим локальную сессию.
    } finally {
      clearSession();
      setBusyLabel("");
    }
  }

  async function refreshLeaderboard(
    topicOverride?: string,
    metricOverride?: LeaderboardMetric,
  ) {
    const topic = topicOverride ?? currentRoute?.topic ?? routes[0]?.topic;
    if (!topic) {
      return;
    }

    const response = await getLeaderboard(topic, metricOverride ?? leaderboardMetric);
    setLeaderboard(response.entries);
    setLeaderboardMetric(response.metric);
    setLeaderboardMetricLabel(response.metric_label);
    setLeaderboardScope(response.scope);
  }

  async function openLeaderboard(
    topicOverride?: string,
    metricOverride?: LeaderboardMetric,
  ) {
    const route =
      routes.find((item) => item.topic === topicOverride) ??
      currentRoute ??
      routes[0] ??
      null;

    if (!route) {
      return;
    }

    setBusyLabel("Загружаем таблицу лидеров...");
    setErrorMessage("");

    try {
      await refreshLeaderboard(route.topic, metricOverride);
      setCurrentRoute(route);
      setView("leaderboard");
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function openAdmin(topicOverride?: string) {
    if (!user?.is_admin) {
      return;
    }

    setBusyLabel("Загружаем панель управления...");
    setErrorMessage("");

    try {
      const routeResponse = await getRoutes();
      const nextRoutes = routeResponse.items;
      const route =
        nextRoutes.find((item) => item.topic === topicOverride) ??
        nextRoutes.find((item) => item.topic === currentRoute?.topic) ??
        nextRoutes[0] ??
        null;
      const shouldResetForms =
        Boolean(topicOverride) && topicOverride !== currentRoute?.topic;

      if (!route) {
        return;
      }

      const data = await getAdminQuestions(route.topic);
      setRoutes(nextRoutes);
      setCurrentRoute(route);
      setSelectedLanguage(route.language);
      setAdminQuestions(data);
      setSelectedAdminQuestionId((prev) =>
        data.some((question) => question.id === prev) ? prev : (data[0]?.id ?? null),
      );
      setDraft((prev) =>
        shouldResetForms || prev.topic !== route.topic ? createEmptyDraft(route.topic) : prev,
      );
      setView("admin");
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function handleAdminRouteChange(nextTopic: string) {
    if (!user?.is_admin) {
      return;
    }
    setDraft((prev) => ({ ...prev, topic: nextTopic }));
    await openAdmin(nextTopic);
  }

  async function openShop() {
    if (!user) {
      return;
    }

    setBusyLabel("Загружаем магазин...");
    setErrorMessage("");

    try {
      const response = await getShop();
      setUser(response.user);
      setShopItems(response.items);
      if (response.message) {
        setSuccessMessage(response.message);
      }
      setView("shop");
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  function openAccount() {
    if (!user) {
      return;
    }

    const fallbackRoute =
      (currentRoute && currentRoute.language === selectedLanguage ? currentRoute : null) ??
      routes.find((route) => route.language === selectedLanguage) ??
      currentRoute ??
      routes[0] ??
      null;

    setErrorMessage("");
    setSuccessMessage("");
    resetAccountForm(user);
    if (fallbackRoute) {
      setAccountRouteTopic(fallbackRoute.topic);
    }
    setView("account");
  }

  async function openAccountRoute(route: RouteOption | null) {
    if (!route) {
      return;
    }

    setSelectedLanguage(route.language);
    setAccountRouteTopic(route.topic);

    if (currentRoute?.topic === route.topic && progress?.topic === route.topic) {
      setView("difficulty");
      return;
    }

    await loadRoute(route, "difficulty");
  }

  async function handleAccountSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) {
      return;
    }

    const displayName = accountForm.displayName.trim();
    const currentPassword = accountForm.currentPassword.trim();
    const newPassword = accountForm.newPassword.trim();
    const confirmPassword = accountForm.confirmPassword.trim();

    if (newPassword !== confirmPassword) {
      setErrorMessage("Новый пароль и подтверждение должны совпадать.");
      setSuccessMessage("");
      return;
    }

    if (currentPassword && !newPassword) {
      setErrorMessage("Чтобы сменить пароль, укажите новый пароль.");
      setSuccessMessage("");
      return;
    }

    setBusyLabel("Сохраняем профиль...");
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const payload: AccountUpdatePayload = {
        display_name: displayName,
      };

      if (currentPassword) {
        payload.current_password = currentPassword;
      }

      if (newPassword) {
        payload.new_password = newPassword;
      }

      const nextUser = await updateProfile(payload);
      setUser(nextUser);
      resetAccountForm(nextUser);
      setSuccessMessage("Профиль обновлен.");

      if (currentRoute || leaderboard.length > 0) {
        await refreshLeaderboard(currentRoute?.topic, leaderboardMetric);
      }
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function handlePromoSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) {
      return;
    }

    const code = promoCode.trim();
    if (!code) {
      setErrorMessage("Введите промокод.");
      setSuccessMessage("");
      return;
    }

    setBusyLabel("Проверяем промокод...");
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const payload: PromoRedeemPayload = { code };
      const response = await redeemPromoCode(payload);
      setUser(response.user);
      replaceProgressCache(response.progresses);
      if (currentRoute) {
        const nextProgress =
          response.progresses.find((item) => item.topic === currentRoute.topic) ?? null;
        if (nextProgress) {
          setProgress(nextProgress);
          setDisplayIndex(nextProgress.current_index);
        }
      }
      setPromoCode("");
      setSuccessMessage(response.message);

      if (leaderboardMetric === "coins") {
        await refreshLeaderboard(undefined, "coins");
      }
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function handleShopItemAction(itemId: string) {
    if (!user) {
      return;
    }

    setBusyLabel("Обновляем каталог предметов...");
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const response = await buyOrEquipShopItem(itemId);
      setUser(response.user);
      setShopItems(response.items);
      setSuccessMessage(response.message ?? "Данные магазина обновлены.");

      if (leaderboardMetric === "coins") {
        await refreshLeaderboard(undefined, "coins");
      }
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function chooseDifficulty(route: RouteOption) {
    await loadRoute(route, "difficulty");
  }

  async function startLevel(levelIndex: number) {
    if (!user || !progress || !currentRoute) {
      return;
    }

    setBusyLabel("Подготавливаем уровень...");
    setErrorMessage("");
    setSuccessMessage("");

    try {
      let nextProgress = progress;

      if (levelIndex !== progress.current_level_index) {
        nextProgress = await selectLevel({
          topic: currentRoute.topic,
          level_index: levelIndex,
        });
        setProgress(nextProgress);
        rememberProgress(nextProgress);
      }

      const isContinuingCurrentLevel =
        levelIndex === progress.current_level_index && progress.current_task_index > 0;
      const nextHearts = isContinuingCurrentLevel
        ? getStoredHearts(
            currentRoute.topic,
            nextProgress.current_level_index,
            nextProgress.remaining_hearts,
          )
        : HEARTS_PER_LEVEL;

      setDisplayIndex(nextProgress.current_index);
      syncLevelHearts(currentRoute.topic, nextProgress.current_level_index, nextHearts);
      setShowHint(false);
      setRoundResult(null);
      resetQuestionUi();
      setView("quiz");
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function resetCurrentRoute(openQuizImmediately = false) {
    if (!user || !currentRoute) {
      return;
    }

    setBusyLabel("Сбрасываем прогресс маршрута...");
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const nextProgress = await resetProgress(currentRoute.topic);
      setProgress(nextProgress);
      rememberProgress(nextProgress);
      setDisplayIndex(nextProgress.current_index);
      clearRouteHearts(currentRoute.topic);
      syncLevelHearts(currentRoute.topic, nextProgress.current_level_index, HEARTS_PER_LEVEL);
      setShowHint(false);
      resetQuestionUi();
      setRoundResult(null);
      setView(openQuizImmediately ? "quiz" : "difficulty");
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function handleResetAllProgress() {
    if (!user) {
      return;
    }

    const confirmed = window.confirm(
      "Сбросить прогресс по всем маршрутам? Монеты, покупки и данные профиля сохранятся.",
    );
    if (!confirmed) {
      return;
    }

    setBusyLabel("Сбрасываем общий прогресс...");
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const response = await resetAllProgress();
      replaceProgressCache(response.items);
      setRoundResult(null);
      resetHeartsState();
      setShowHint(false);
      resetQuestionUi();

      if (currentRoute) {
        const nextProgress =
          response.items.find((item) => item.topic === currentRoute.topic) ?? null;
        if (nextProgress) {
          setProgress(nextProgress);
          setDisplayIndex(nextProgress.current_index);
        }
      } else {
        setProgress(null);
        setDisplayIndex(0);
      }

      setSuccessMessage("Прогресс по всем маршрутам сброшен.");
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function handleSubmitAnswer() {
    if (!user || !currentRoute || !currentQuestion || !canSubmitAnswer) {
      return;
    }

    setBusyLabel("Проверяем ответ...");
    setErrorMessage("");

    try {
      const result = await submitAnswer({
        topic: currentRoute.topic,
        question_id: currentQuestion.id,
        answer: currentAnswer,
      });
      setUser(result.user);

      let nextFeedbackAction: FeedbackAction = "retry";
      let nextProgress = result.next_progress;

      if (result.is_correct) {
        nextFeedbackAction = "advance";

        if (result.quiz_completed) {
          setRoundResult({
            finalScore: result.final_score ?? 0,
            totalQuestions: result.total_questions,
            bestScore: result.next_progress.best_score,
            completedRuns: result.next_progress.completed_runs,
            routeTitle: getRouteTitle(currentRoute),
          });
          await refreshLeaderboard(currentRoute.topic, leaderboardMetric);
        }
      } else {
        const remainingHearts = hearts - 1;
        if (remainingHearts <= 0) {
          nextProgress = await resetLevel({ topic: currentRoute.topic });
          nextFeedbackAction = "level-reset";
          syncLevelHearts(currentRoute.topic, currentQuestion.level_index, 0);
        } else {
          syncLevelHearts(currentRoute.topic, currentQuestion.level_index, remainingHearts);
          nextFeedbackAction = "retry";
        }
      }

      setFeedback(result);
      setFeedbackAction(nextFeedbackAction);
      setPendingProgress(nextProgress);
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  function handleNextAfterFeedback() {
    if (!feedback || !currentRoute || !currentQuestion) {
      return;
    }

    if (feedback.quiz_completed) {
      if (pendingProgress) {
        setProgress(pendingProgress);
        rememberProgress(pendingProgress);
      }
      clearRouteHearts(currentRoute.topic);
      setDisplayIndex(0);
      setHearts(HEARTS_PER_LEVEL);
      setShowHint(false);
      resetQuestionUi();
      setView("result");
      return;
    }

      if (feedbackAction === "advance" && pendingProgress) {
        setProgress(pendingProgress);
        rememberProgress(pendingProgress);
        setDisplayIndex(pendingProgress.current_index);
        if (pendingProgress.current_level_index !== currentQuestion.level_index) {
          syncLevelHearts(currentRoute.topic, pendingProgress.current_level_index, HEARTS_PER_LEVEL);
        } else {
          setHearts(
            getStoredHearts(
              currentRoute.topic,
              currentQuestion.level_index,
              pendingProgress.remaining_hearts,
            ),
          );
        }
        setShowHint(false);
      }

    if (feedbackAction === "level-reset" && pendingProgress) {
      setProgress(pendingProgress);
      rememberProgress(pendingProgress);
      setDisplayIndex(pendingProgress.current_index);
      syncLevelHearts(currentRoute.topic, pendingProgress.current_level_index, HEARTS_PER_LEVEL);
      setShowHint(false);
    }

    resetQuestionUi();
  }

  function beginEditQuestion(question: AdminQuestion) {
    setEditingQuestionId(question.id);
    setSelectedAdminQuestionId(question.id);
    setDraft({
      topic: question.topic,
      type: question.type,
      prompt: question.prompt,
      explanation: question.explanation,
      placeholder: question.placeholder ?? "",
      order_index: String(question.order_index),
      options_text: question.options.join("\n"),
      answers_text: question.correct_answers.join("\n"),
    });
    setSuccessMessage("Вопрос открыт для редактирования.");
    setErrorMessage("");
  }

  function buildPayloadFromDraft(): AdminQuestionPayload {
    const orderIndex = Number.parseInt(draft.order_index || "0", 10);
    const options = draft.options_text
      .split("\n")
      .map((item) => normalizeWhitespace(item))
      .filter(Boolean);
    const answers = draft.answers_text
      .split("\n")
      .map((item) => normalizeWhitespace(item))
      .filter(Boolean);

    return {
      topic: draft.topic.trim().toLowerCase() || currentRoute?.topic || DEFAULT_TOPIC,
      type: draft.type,
      prompt: normalizeWhitespace(draft.prompt),
      explanation: normalizeWhitespace(draft.explanation),
      placeholder: draft.placeholder.trim() || null,
      order_index: Number.isNaN(orderIndex) ? 0 : orderIndex,
      options,
      correct_answers: answers,
    };
  }

  async function handleSaveQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user?.is_admin) {
      return;
    }

    setBusyLabel(editingQuestionId ? "Сохраняем вопрос..." : "Добавляем вопрос...");
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const payload = buildPayloadFromDraft();

      if (editingQuestionId) {
        await updateAdminQuestion(editingQuestionId, payload);
        setSuccessMessage("Вопрос обновлен.");
      } else {
        await createAdminQuestion(payload);
        setSuccessMessage("Вопрос добавлен.");
      }

      resetDraftForm(payload.topic);
      await openAdmin(payload.topic);
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function handleDeleteQuestion(questionId: number) {
    if (!user?.is_admin) {
      return;
    }

    const confirmed = window.confirm("Удалить вопрос?");
    if (!confirmed) {
      return;
    }

    setBusyLabel("Удаляем вопрос...");
    setErrorMessage("");
    setSuccessMessage("");

    try {
      await deleteAdminQuestion(questionId);
      if (editingQuestionId === questionId) {
        resetDraftForm();
      }
      setSuccessMessage("Вопрос удален.");
      await openAdmin(draft.topic);
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  function renderTopNav() {
    if (!user) {
      return null;
    }

    return (
      <div className="top-nav">
        <div className="top-nav__identity">
          <FrogAvatar
            accessory={user.active_skin}
            className="top-nav__frog"
            frogClassName="top-nav__frog-svg"
            frogSize={46}
          />
          <div>
            <strong>{getUserHandle(user)}</strong>
            <span>
              {currentRoute
                ? `Маршрут: ${getRouteTitle(currentRoute)}`
                : "Выберите язык и сложность"}
            </span>
            <div className="top-nav__chips">
              {user.tag && <span className="top-nav__chip">🏷️ #{user.tag}</span>}
              <span className="top-nav__chip">💰 {user.coins}</span>
              <span className="top-nav__chip top-nav__chip--skin">
                {user.active_skin_icon} {user.active_skin_label}
              </span>
            </div>
          </div>
        </div>

        <div className="top-nav__actions">
          <button className="button button--ghost" onClick={() => setView("menu")}>
            Главная
          </button>
          <button className="button button--ghost" onClick={openAccount}>
            Аккаунт
          </button>
          <button
            className="button button--ghost"
            onClick={() => setView(currentRoute ? "difficulty" : "menu")}
          >
            Уровни
          </button>
          <button
            className="button button--ghost"
            onClick={() => void openLeaderboard()}
          >
            Лидеры
          </button>
          <button className="button button--ghost" onClick={() => void openShop()}>
            Магазин
          </button>
          {user.is_admin && (
            <button className="button button--ghost" onClick={() => void openAdmin()}>
              Админка
            </button>
          )}
          <button className="button button--ghost" onClick={handleLogout}>
            Выйти
          </button>
        </div>
      </div>
    );
  }

  function renderStatusBar() {
    if (!busyLabel && !errorMessage && !successMessage) {
      return null;
    }

    return (
      <div className="status-stack">
        {busyLabel && <div className="status-box status-box--busy">{busyLabel}</div>}
        {errorMessage && <div className="status-box status-box--error">{errorMessage}</div>}
        {successMessage && (
          <div className="status-box status-box--success">{successMessage}</div>
        )}
      </div>
    );
  }

  function renderAuthView() {
    return (
      <section className="card card--auth">
        <div className="auth-layout">
          <div className="auth-overview" style={AUTH_SCENE_STYLE}>
            <div className="auth-overview__glass">
              <div className="auth-overview__intro">
                <h2>Аккаунт Froggy Coder</h2>
                <p className="auth-overview__text">
                  Вход в приложение с маршрутами по программированию, прогрессом по уровням
                  и наградами за правильные ответы.
                </p>
              </div>

              <div className="auth-benefits">
                <article className="auth-benefit">
                  <span className="auth-benefit__icon" aria-hidden="true">
                    🗺️
                  </span>
                  <div>
                    <strong>Маршруты и уровни</strong>
                    <p>
                      Выбирайте язык, сложность и проходите уровни по Python и
                      JavaScript в удобном темпе.
                    </p>
                  </div>
                </article>

                <article className="auth-benefit">
                  <span className="auth-benefit__icon" aria-hidden="true">
                    💾
                  </span>
                  <div>
                    <strong>Прогресс сохраняется</strong>
                    <p>
                      Аккаунт хранит открытые уровни, статистику маршрутов, монеты и
                      выбранные аксессуары.
                    </p>
                  </div>
                </article>

                <article className="auth-benefit">
                  <span className="auth-benefit__icon" aria-hidden="true">
                    🏆
                  </span>
                  <div>
                    <strong>Награды и рейтинг</strong>
                    <p>
                      Получайте монеты за правильные ответы, открывайте предметы в
                      магазине и поднимайтесь в таблице лидеров.
                    </p>
                  </div>
                </article>
              </div>
            </div>
          </div>

          <div className="auth-form-card">
            <div className="auth-form-card__header">
              <div>
                <p className="auth-kicker">
                  {authMode === "register" ? "Новый аккаунт" : "С возвращением"}
                </p>
                <h3>
                  {authMode === "register" ? "Создать аккаунт" : "Войти в аккаунт"}
                </h3>
              </div>
              <span className="auth-form-card__emoji" aria-hidden="true">
                🐸
              </span>
            </div>

            <p className="auth-form-card__text">
              {authMode === "register"
                ? "Создайте профиль, чтобы сохранять прогресс, монеты и купленные аксессуары. Уникальный тег будет назначен автоматически."
                : "Войдите, чтобы продолжить с сохраненного места. Можно использовать имя пользователя или логин в формате имя#тег."}
            </p>

            <form className="auth-form" onSubmit={handleAuthSubmit}>
              <div className="auth-switch">
                <button
                  type="button"
                  className={`auth-switch__btn ${
                    authMode === "register" ? "auth-switch__btn--active" : ""
                  }`}
                  onClick={() => setAuthMode("register")}
                >
                  Регистрация
                </button>
                <button
                  type="button"
                  className={`auth-switch__btn ${
                    authMode === "login" ? "auth-switch__btn--active" : ""
                  }`}
                  onClick={() => setAuthMode("login")}
                >
                  Вход
                </button>
              </div>

              <label className="field field--auth">
                <span>
                  {authMode === "login" ? "Имя пользователя или имя#тег" : "Имя пользователя"}
                </span>
                <input
                  value={authForm.username}
                  onChange={(event) =>
                    setAuthForm((prev) => ({ ...prev, username: event.target.value }))
                  }
                  placeholder={authMode === "login" ? "frog_coder#1234" : "frog_coder"}
                />
              </label>

              <label className="field field--auth">
                <span>Пароль</span>
                <input
                  type="password"
                  value={authForm.password}
                  onChange={(event) =>
                    setAuthForm((prev) => ({ ...prev, password: event.target.value }))
                  }
                  placeholder="Минимум 6 символов"
                />
              </label>

              <button className="button button--primary" type="submit">
                {authMode === "login" ? "Войти" : "Создать аккаунт"}
              </button>
            </form>

            <div className="auth-footnote">
              <span>Языки: Python и JavaScript</span>
              <span>Уровни сложности: Easy / Medium / Hard</span>
            </div>
          </div>
        </div>
      </section>
    );
  }

  function renderMenuView() {
    const currentRuns = currentRoute ? routeProgressCache[currentRoute.topic]?.completed_runs ?? 0 : 0;
    const currentCoins = user?.coins ?? 0;

    return (
      <section className="card">
        <div className="scene-layout">
          <div className="scene-copy">
            <div className="card-badge">Главное меню</div>
            <h2>Выберите язык и откройте нужный маршрут</h2>
            <p className="card-text">
              Каждый маршрут разбит по сложности и уровням. Прогресс, монеты и результаты
              сохраняются автоматически в профиле.
            </p>

            <div className="stats-row">
              <article className="stat-box">
                <span className="stat-label">Языков</span>
                <strong>{languageOptions.length}</strong>
              </article>

              <article className="stat-box">
                <span className="stat-label">Маршрутов</span>
                <strong>{routes.length}</strong>
              </article>

              <article className="stat-box">
                <span className="stat-label">Монет в кошельке</span>
                <strong>{currentCoins}</strong>
              </article>
            </div>
          </div>

          <div className="scene-art" style={MENU_SCENE_STYLE}>
            <div className="frog-bubble">
              Выберите язык программирования, затем откройте нужную сложность и
              продолжайте с последнего доступного уровня.
            </div>

            <div className="preview-panel">
              <h3>Что доступно</h3>
              <p>
                Маршруты, уровни, подсказки, жизни, магазин и таблица лидеров уже
                доступны в приложении.
              </p>
            </div>

            <FrogFamily />

            <p className="scene-caption">
              Текущий маршрут: {currentRoute ? getRouteTitle(currentRoute) : "не выбран"}
            </p>
          </div>
        </div>

        <div className="route-grid">
          {languageOptions.map((language) => (
            <button
              key={language}
              type="button"
              className={`route-card ${
                selectedLanguage === language ? "route-card--active" : ""
              }`}
              onClick={() => {
                setSelectedLanguage(language);
                setView("difficulty");
              }}
            >
              <span className="route-card__eyebrow">Язык</span>
              <strong>{language}</strong>
              <span>
                {routes.filter((route) => route.language === language).length} маршрута
              </span>
            </button>
          ))}
        </div>

        <div className="actions-row">
          <button className="button button--ghost" onClick={openAccount}>
            Аккаунт
          </button>
          <button className="button button--ghost" onClick={() => void openShop()}>
            Открыть магазин
          </button>
          <button className="button button--ghost" onClick={() => void openLeaderboard()}>
            Таблица лидеров
          </button>
          <button
            className="button button--ghost button--danger"
            onClick={() => void handleResetAllProgress()}
          >
            Сбросить весь прогресс
          </button>
          <span className="account-chip">Прохождений текущего маршрута: {currentRuns}</span>
        </div>
      </section>
    );
  }

  function renderDifficultyView() {
    const activeRoute =
      currentRoute && currentRoute.language === selectedLanguage ? currentRoute : null;
    const activeProgress = activeRoute
      ? routeProgressCache[activeRoute.topic] ??
        (progress?.topic === activeRoute.topic ? progress : null)
      : null;
    const hasActiveQuestions = (activeRoute?.questions_total ?? 0) > 0;
    const levels = activeRoute
      ? Array.from({ length: activeRoute.levels_total }, (_, index) => index)
      : [];

    return (
      <section className="card">
        <div className="card-badge">Сложность</div>
        <h2>{selectedLanguage}: выберите уровень сложности</h2>
        <p className="card-text">
          Для каждой сложности доступен отдельный маршрут с собственным прогрессом,
          статистикой и набором уровней.
        </p>

        <div className="route-grid">
          {difficultyOptions.map((route) => {
            const savedProgress = routeProgressCache[route.topic];
            const isActiveRoute = activeRoute?.topic === route.topic;
            return (
              <article key={route.topic} className="route-card route-card--panel">
                <span className="route-card__eyebrow">{route.language}</span>
                <strong>{route.difficulty_label}</strong>
                <span>{route.questions_total} заданий</span>
                <span>{getRouteContentHint(route)}</span>
                <span>
                  {savedProgress
                    ? `Открыт уровень ${savedProgress.unlocked_level_index + 1}`
                    : "Еще не запускался"}
                </span>

                <button
                  className="button button--primary"
                  type="button"
                  onClick={() => void chooseDifficulty(route)}
                >
                  {isActiveRoute ? "Обновить маршрут" : "Открыть маршрут"}
                </button>
              </article>
            );
          })}
        </div>

        {activeRoute && activeProgress && hasActiveQuestions && (
          <>
            <div className="card-badge">Уровни маршрута</div>
            <h3>{getRouteTitle(activeRoute)}</h3>
            <p className="card-text">
              Продолжайте с последней точки или запускайте любой доступный уровень.
              Сейчас активны уровень {activeProgress.current_level_index + 1} и задание{" "}
              {activeProgress.current_task_index + 1}.
            </p>

            <div className="map-summary">
              <span className="account-chip">
                Открыт уровень: {activeProgress.unlocked_level_index + 1}
              </span>
              <span className="account-chip">
                Завершенных забегов: {activeProgress.completed_runs}
              </span>
              <span className="account-chip">
                Лучший счет: {activeProgress.best_score}
              </span>
              <span className="account-chip">Монеты: {user?.coins ?? 0}</span>
            </div>

            <div className="level-map">
              {levels.map((levelIndex) => {
                const isUnlocked = levelIndex <= activeProgress.unlocked_level_index;
                const isCurrent = levelIndex === activeProgress.current_level_index;
                const isReplayable = levelIndex < activeProgress.current_level_index;
                const statusClass = isUnlocked
                  ? isCurrent
                    ? "map-node--current"
                    : "map-node--done"
                  : "map-node--locked";
                const nodeText = isCurrent
                  ? `Задание ${activeProgress.current_task_index + 1}/${activeProgress.tasks_per_level}`
                  : isUnlocked
                    ? isReplayable
                      ? "Доступен повтор"
                      : "Доступен"
                    : "Недоступен";
                const buttonText =
                  levelIndex === activeProgress.current_level_index &&
                  activeProgress.current_task_index > 0
                    ? "Продолжить"
                    : isReplayable
                      ? "Пройти заново"
                      : "Начать";

                return (
                  <article key={levelIndex} className={`map-node ${statusClass}`}>
                    <div className="map-node__circle">{levelIndex + 1}</div>
                    <strong>Уровень {levelIndex + 1}</strong>
                    <span>{nodeText}</span>

                    {isUnlocked ? (
                      <button
                        type="button"
                        className="button button--primary"
                        onClick={() => void startLevel(levelIndex)}
                      >
                        {buttonText}
                      </button>
                    ) : (
                      <button type="button" className="button button--ghost" disabled>
                        Недоступен
                      </button>
                    )}
                  </article>
                );
              })}
            </div>

            <div className="actions-row">
              <button className="button button--ghost" onClick={() => setView("menu")}>
                К языкам
              </button>
              <button
                className="button button--ghost"
                onClick={() => void resetCurrentRoute(false)}
              >
                Сбросить прогресс маршрута
              </button>
            </div>
          </>
        )}

        {activeRoute && activeProgress && !hasActiveQuestions && (
          <>
            <div className="card-badge">Уровни маршрута</div>
            <h3>{getRouteTitle(activeRoute)}</h3>
            <div className="empty-state">
              Для этого маршрута пока нет заданий. Контент для маршрута еще не добавлен.
            </div>

            <div className="actions-row">
              <button className="button button--ghost" onClick={() => setView("menu")}>
                К языкам
              </button>
              {user?.is_admin && (
                <button
                  className="button button--primary"
                  onClick={() => void openAdmin(activeRoute.topic)}
                >
                  Открыть админку
                </button>
              )}
            </div>
          </>
        )}

        {!activeRoute && (
          <div className="actions-row">
            <button className="button button--ghost" onClick={() => setView("menu")}>
              К языкам
            </button>
          </div>
        )}
      </section>
    );
  }

  function renderQuizView() {
    if (!currentQuestion || !progress || !currentRoute) {
      return null;
    }

    const currentLevelQuestions = questions.filter(
      (question) => question.level_index === currentQuestion.level_index,
    );
    const heartsLeft = Array.from({ length: HEARTS_PER_LEVEL }, (_, index) => index < hearts);
    const questionHint =
      currentQuestion.hint.trim().length > 0
        ? currentQuestion.hint
        : currentQuestion.placeholder?.trim() || "Подсказка для этого задания пока не добавлена.";
    const actionLabel =
      feedback === null
        ? "Проверить ответ"
        : feedback.quiz_completed
          ? "К результатам"
          : feedbackAction === "level-reset"
            ? "Начать уровень заново"
            : feedbackAction === "advance"
              ? "Следующее задание"
              : "Повторить попытку";

    return (
      <section className="card card--quiz">
        <div className="quiz-topbar">
          <div>
            <p className="eyebrow">{getRouteTitle(currentRoute)}</p>
            <h2>Уровень {currentQuestion.level_index + 1}</h2>
          </div>

          <div className="quiz-meta">
            <span>
              Задание {currentQuestion.task_index + 1} / {progress.tasks_per_level}
            </span>
            <span>Пройдено задач: {progress.current_score}</span>
          </div>
        </div>

        <div className="quiz-strip">
          <div className="task-dots" aria-label="Прогресс внутри уровня">
            {currentLevelQuestions.map((question) => {
              const isCurrent = question.id === currentQuestion.id;
              const isDone = question.task_index < currentQuestion.task_index;

              return (
                <div
                  key={question.id}
                  className={`task-dot ${
                    isDone
                      ? "task-dot--done"
                      : isCurrent
                        ? "task-dot--current"
                        : "task-dot--next"
                  }`}
                  aria-hidden="true"
                />
              );
            })}
          </div>

          <div className="hearts-bar" aria-label="Сердца">
            {heartsLeft.map((isAlive, index) => (
              <span key={index} className={isAlive ? "heart heart--alive" : "heart"}>
                {isAlive ? "❤️" : "🖤"}
              </span>
            ))}
          </div>
        </div>

        <div className="question-box">
          <p className="question-number">Задание маршрута</p>
          <h3>{currentQuestion.prompt}</h3>
        </div>

        <div className="hint-panel">
          <button
            className="button button--ghost"
            type="button"
            onClick={() => setShowHint((prev) => !prev)}
          >
            {showHint ? "Скрыть подсказку" : "Показать подсказку"}
          </button>

          {showHint && <p>{questionHint}</p>}
        </div>

        {currentQuestion.type === "choice" ? (
          <div className="options-grid">
            {currentQuestion.options.map((option) => {
              const isSelected = selectedOption === option;
              const isCorrectOption = feedback?.correct_answers.includes(option);
              const classes = [
                "option-card",
                isSelected ? "option-card--selected" : "",
                feedback && isCorrectOption ? "option-card--correct" : "",
                feedback && isSelected && !feedback.is_correct
                  ? "option-card--wrong"
                  : "",
              ]
                .filter(Boolean)
                .join(" ");

              return (
                <button
                  key={option}
                  type="button"
                  className={classes}
                  disabled={feedback !== null}
                  onClick={() => setSelectedOption(option)}
                >
                  <span className="option-marker" />
                  <span>{option}</span>
                </button>
              );
            })}
          </div>
        ) : (
          <label className="field">
            <span>Ответ</span>
            <input
              value={typedAnswer}
              placeholder={currentQuestion.placeholder ?? "Введите ответ"}
              onChange={(event) => setTypedAnswer(event.target.value)}
              autoCapitalize="none"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              translate="no"
              disabled={feedback !== null}
            />
          </label>
        )}

        {feedback && (
          <div
            className={`status-box ${
              feedback.is_correct ? "status-box--success" : "status-box--warning"
            }`}
          >
            <strong>
              {feedback.is_correct
                ? `Правильно. +${feedback.coins_awarded} монет.`
                : feedbackAction === "level-reset"
                  ? "Попытки закончились. Уровень начнется заново."
                  : `Неверно. Осталось жизней: ${hearts}.`}
            </strong>
            {!feedback.is_correct && (
              <span>Правильный ответ: {feedback.correct_answers.join(" или ")}</span>
            )}
          </div>
        )}

        <div className="actions-row">
          <button
            className="button button--primary"
            onClick={feedback ? handleNextAfterFeedback : () => void handleSubmitAnswer()}
            disabled={!feedback && !canSubmitAnswer}
          >
            {actionLabel}
          </button>

          <button className="button button--ghost" onClick={() => setView("difficulty")}>
            К уровням
          </button>
        </div>
      </section>
    );
  }

  function renderResultView() {
    if (!roundResult || !currentRoute) {
      return null;
    }

    return (
      <section className="card">
        <div className="scene-layout">
          <div className="scene-copy">
            <div className="card-badge">Результаты</div>
            <h2>Маршрут завершен: {roundResult.routeTitle}</h2>
            <p className="score-line">
              Пройдено <strong>{roundResult.finalScore}</strong> из{" "}
              <strong>{roundResult.totalQuestions}</strong> заданий.
            </p>
            <p className="card-text">
              Лучший результат на этом маршруте: <strong>{roundResult.bestScore}</strong>.
              Всего завершенных прохождений: <strong>{roundResult.completedRuns}</strong>.
            </p>

            <div className="result-ring">
              <span>100%</span>
            </div>

            <div className="actions-row">
              <button
                className="button button--primary"
                onClick={() => void resetCurrentRoute(true)}
              >
                Играть снова
              </button>
              <button className="button button--ghost" onClick={() => setView("difficulty")}>
                К уровням
              </button>
              <button
                className="button button--ghost"
                onClick={() => void openLeaderboard(currentRoute.topic)}
              >
                Лидеры
              </button>
            </div>
          </div>

          <div className="scene-art" style={RESULT_SCENE_STYLE}>
            <div className="frog-bubble frog-bubble--result">
              Финиш! Результат сохранен в профиле, а лучший рекорд учтен в таблице
              лидеров.
            </div>

            <div className="preview-panel">
              <h3>Что сохраняется после финиша</h3>
              <p>
                Прогресс по маршрутам, завершенные прохождения, монеты и купленные
                предметы сохраняются в аккаунте автоматически.
              </p>
            </div>

            <FrogFamily />

            <p className="scene-caption">
              Можно пройти маршрут еще раз, улучшить рекорд или выбрать новый
              маршрут.
            </p>
          </div>
        </div>
      </section>
    );
  }

  function renderAccountView() {
    if (!user) {
      return null;
    }

    const trackedRoute =
      routes.find((route) => route.topic === accountRouteTopic) ??
      (currentRoute && currentRoute.language === selectedLanguage ? currentRoute : null) ??
      routes.find((route) => route.language === selectedLanguage) ??
      currentRoute ??
      routes[0] ??
      null;
    const trackedProgress = trackedRoute
      ? routeProgressCache[trackedRoute.topic] ??
        (progress?.topic === trackedRoute.topic ? progress : null)
      : null;
    const routeLabel = trackedRoute ? getRouteTitle(trackedRoute) : "Маршрут не выбран";
    const currentDisplayName = accountForm.displayName.trim() || user.username;
    const loginPreview = user.tag ? `${currentDisplayName}#${user.tag}` : currentDisplayName;
    const openedQuestions = trackedProgress?.opened_questions ?? 0;
    const progressPercent =
      trackedProgress && trackedProgress.total_questions > 0
        ? Math.round((openedQuestions / trackedProgress.total_questions) * 100)
        : 0;

    return (
      <section className="card">
        <div className="account-shell">
          <div className="account-hero" style={MENU_SCENE_STYLE}>
            <div className="account-hero__content">
              <div className="account-hero__topline">
                <FrogAvatar
                  accessory={user.active_skin}
                  className="account-avatar"
                  frogClassName="account-avatar__frog"
                  frogSize={62}
                />

                <div>
                  <p className="account-kicker">Профиль</p>
                  <h2>{loginPreview}</h2>
                  <p className="account-subtitle">
                    Здесь можно обновить имя пользователя и пароль. Уникальный тег
                    сохраняется и остается частью логина.
                  </p>
                </div>
              </div>

              <div className="account-rankline">
                <span className="account-chip">Тег: #{user.tag ?? "----"}</span>
                <span className="account-chip">Маршрут: {routeLabel}</span>
                <span className="account-chip">
                  Образ: {user.active_skin_icon} {user.active_skin_label}
                </span>
                <span className="account-chip">Монеты: {user.coins}</span>
              </div>
            </div>
          </div>

          <div className="account-grid">
            <div className="account-panel">
              <div className="account-panel__header">
                <div>
                  <p className="account-panel__eyebrow">Аккаунт</p>
                  <h3>Настройки профиля</h3>
                </div>
                <span className="account-progress-badge">Логин: {loginPreview}</span>
              </div>

              <form className="account-form" onSubmit={handleAccountSubmit}>
                <label className="field">
                  <span>Имя пользователя</span>
                  <input
                    value={accountForm.displayName}
                    onChange={(event) =>
                      setAccountForm((prev) => ({
                        ...prev,
                        displayName: event.target.value,
                      }))
                    }
                    autoCapitalize="none"
                    autoComplete="nickname"
                    autoCorrect="off"
                    spellCheck={false}
                    placeholder="frog_coder"
                  />
                </label>

                <div className="account-form__meta">
                  <div className="account-readonly">
                    <span>Тег</span>
                    <strong>#{user.tag ?? "----"}</strong>
                  </div>
                  <div className="account-readonly">
                    <span>Логин для следующих входов</span>
                    <strong>{loginPreview}</strong>
                  </div>
                </div>

                <p className="account-form__hint">
                  Тег закреплен за профилем. При смене имени обновится и полный логин
                  формата `имя#тег`.
                </p>

                <div className="account-form__grid">
                  <label className="field">
                    <span>Текущий пароль</span>
                    <input
                      type="password"
                      value={accountForm.currentPassword}
                      onChange={(event) =>
                        setAccountForm((prev) => ({
                          ...prev,
                          currentPassword: event.target.value,
                        }))
                      }
                      autoComplete="current-password"
                      placeholder="Требуется только при смене пароля"
                    />
                  </label>

                  <label className="field">
                    <span>Новый пароль</span>
                    <input
                      type="password"
                      value={accountForm.newPassword}
                      onChange={(event) =>
                        setAccountForm((prev) => ({
                          ...prev,
                          newPassword: event.target.value,
                        }))
                      }
                      autoComplete="new-password"
                      placeholder="Минимум 6 символов"
                    />
                  </label>
                </div>

                <label className="field">
                  <span>Повторите новый пароль</span>
                  <input
                    type="password"
                    value={accountForm.confirmPassword}
                    onChange={(event) =>
                      setAccountForm((prev) => ({
                        ...prev,
                        confirmPassword: event.target.value,
                      }))
                    }
                    autoComplete="new-password"
                    placeholder="Повторите новый пароль"
                  />
                </label>

                <p className="account-form__hint">
                  Если пароль менять не нужно, оставьте поля пустыми.
                </p>

                <div className="account-actions">
                  <button className="button button--primary" type="submit">
                    Сохранить изменения
                  </button>
                  <button
                    className="button button--ghost"
                    type="button"
                    onClick={() => resetAccountForm(user)}
                  >
                    Сбросить изменения
                  </button>
                </div>
              </form>

              <div className="account-note">
                <span className="account-note__icon" aria-hidden="true">
                  🔐
                </span>
                <div>
                  <strong>Вход после смены имени</strong>
                  <p>
                    После сохранения используйте новый логин <strong>{loginPreview}</strong>.
                    Текущая сессия при этом не прервется.
                  </p>
                </div>
              </div>

            </div>

            <div className="account-side-stack">
              <div className="account-panel">
                <div className="account-panel__header">
                  <div>
                    <p className="account-panel__eyebrow">Прогресс</p>
                    <h3>Статистика маршрута</h3>
                  </div>
                  <span className="account-progress-badge">
                    {trackedRoute ? "Выбран маршрут" : "Маршрут не выбран"}
                  </span>
                </div>

                <label className="field">
                  <span>Маршрут для прогресса</span>
                  <select
                    value={trackedRoute?.topic ?? ""}
                    onChange={(event) => setAccountRouteTopic(event.target.value)}
                  >
                    {routes.map((route) => (
                      <option key={route.topic} value={route.topic}>
                        {route.language} • {route.difficulty_label}
                      </option>
                    ))}
                  </select>
                </label>

                <div className="account-progress-card">
                  <div className="account-progress-card__numbers">
                    <strong>{openedQuestions}</strong>
                    <span>
                      {trackedProgress
                        ? `из ${trackedProgress.total_questions} заданий открыто`
                        : "прогресс по этому маршруту пока не зафиксирован"}
                    </span>
                  </div>

                  <div className="account-progress-track" aria-hidden="true">
                    <div
                      className="account-progress-track__fill"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>

                <div className="account-metrics">
                  <article className="account-metric">
                    <span className="account-metric__label">Лучший счет</span>
                    <strong>{trackedProgress?.best_score ?? 0}</strong>
                  </article>
                  <article className="account-metric">
                    <span className="account-metric__label">Забеги</span>
                    <strong>{trackedProgress?.completed_runs ?? 0}</strong>
                  </article>
                  <article className="account-metric">
                    <span className="account-metric__label">Открыт уровень</span>
                    <strong>{trackedProgress ? trackedProgress.unlocked_level_index + 1 : 1}</strong>
                  </article>
                </div>

                <div className="actions-row">
                  <button
                    className="button button--primary"
                    onClick={() => void openAccountRoute(trackedRoute)}
                  >
                    Открыть маршрут
                  </button>
                  <button className="button button--ghost" onClick={() => void openShop()}>
                    Магазин
                  </button>
                </div>
              </div>

              <div className="account-panel">
                <div className="account-panel__header">
                  <div>
                    <p className="account-panel__eyebrow">Промокод</p>
                    <h3>Бонус для аккаунта</h3>
                  </div>
                  <span className="account-progress-badge">ПРОМОКОД</span>
                </div>

                <form className="account-form" onSubmit={handlePromoSubmit}>
                  <label className="field">
                    <span>Промокод</span>
                    <input
                      value={promoCode}
                      onChange={(event) => setPromoCode(event.target.value.toUpperCase())}
                      autoCapitalize="characters"
                      autoComplete="off"
                      autoCorrect="off"
                      spellCheck={false}
                      placeholder="FROGBEST"
                    />
                  </label>

                  <p className="account-form__hint">
                    Промокод <strong>FROGBEST</strong> открывает все уровни и добавляет
                    <strong> 1000 </strong> монет. Активировать его можно только один раз
                    для каждого аккаунта.
                  </p>

                  <button className="button button--primary" type="submit">
                    Активировать промокод
                  </button>
                </form>
              </div>
            </div>
          </div>
        </div>
      </section>
    );
  }

  function renderLeaderboardView() {
    const routeLabel = currentRoute ? getRouteTitle(currentRoute) : "маршрут не выбран";
    const scopeText =
      leaderboardScope === "global"
        ? "Статистика по всем игрокам."
        : `Статистика для маршрута ${routeLabel}.`;

    return (
      <section className="card">
        <div className="card-badge">Таблица лидеров</div>
        <h2>Таблица лидеров: {leaderboardMetricLabel}</h2>
        <p className="card-text">{scopeText}</p>

        <div className="leaderboard-toolbar">
          <div className="map-summary">
            <span className="account-chip">
              {leaderboardScope === "global" ? "Все маршруты" : routeLabel}
            </span>
            <span className="account-chip">
              Монеты: {user?.coins ?? 0}
            </span>
          </div>
        </div>

        {leaderboard.length === 0 ? (
          <div className="empty-state">
            По этой метрике пока нет данных.
          </div>
        ) : (
          <div className="leaderboard-list">
            {leaderboard.map((entry) => (
              <div
                key={`${entry.rank}-${entry.full_username}`}
                className="leaderboard-row"
              >
                <div className="leaderboard-row__rank">#{entry.rank}</div>
                <div className="leaderboard-row__meta">
                  <strong>{getLeaderboardHandle(entry)}</strong>
                  <span>Последний финиш: {formatDate(entry.last_played_at)}</span>
                </div>
                <div className="leaderboard-row__score">
                  <strong>{leaderboardMetricLabel}: {entry.metric_value}</strong>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="actions-row">
          <button
            className="button button--primary"
            onClick={() => setView(currentRoute ? "difficulty" : "menu")}
          >
            Назад
          </button>
          <button className="button button--ghost" onClick={() => void refreshLeaderboard()}>
            Обновить
          </button>
        </div>
      </section>
    );
  }

  function renderShopView() {
    const ownedCount = shopItems.filter((item) => item.owned).length;

    return (
      <section className="card">
        <div className="scene-layout">
          <div className="scene-copy">
            <div className="card-badge">Магазин</div>
            <h2>Аксессуары и предметы профиля</h2>
            <p className="card-text">
              Покупайте предметы за монеты, которые начисляются за правильные ответы
              в заданиях.
            </p>

            <div className="stats-row">
              <article className="stat-box">
                <span className="stat-label">Монеты</span>
                <strong>{user?.coins ?? 0}</strong>
              </article>

              <article className="stat-box">
                <span className="stat-label">Открыто предметов</span>
                <strong>{ownedCount}</strong>
              </article>

              <article className="stat-box">
                <span className="stat-label">Активный образ</span>
                <strong>
                  {user?.active_skin_icon} {user?.active_skin_label}
                </strong>
              </article>
            </div>

            <div className="frog-showcase">
              <PrimitiveFrog
                size={156}
                color="#32c832"
                accessory={user?.active_skin}
                containAccessory
                className="frog-showcase__frog"
              />
              <div className="frog-showcase__badge">
                <span>{user?.active_skin_icon}</span>
                <strong>{user?.active_skin_label}</strong>
              </div>
            </div>
          </div>

          <div className="scene-art" style={MENU_SCENE_STYLE}>
            <div className="frog-bubble">
              Активный предмет меняет внешний вид лягушки в профиле и в верхней панели.
            </div>

            <div className="preview-panel">
              <h3>Как зарабатываются монеты</h3>
              <p>
                За каждый правильный ответ начисляется `+10` монет. Ошибки не
                списывают уже накопленный баланс.
              </p>
            </div>

            <FrogFamily />
          </div>
        </div>

        <div className="shop-grid">
          {shopItems.map((item) => {
            const actionLabel = item.active
              ? "Используется"
              : item.owned
                ? "Выбрать"
                : `Купить за ${item.price}`;

            return (
              <article key={item.id} className={`shop-card ${item.active ? "shop-card--active" : ""}`}>
                <div className="shop-card__head">
                  <span className="shop-card__icon" aria-hidden="true">
                    {item.icon}
                  </span>
                  <div>
                    <strong>{item.name}</strong>
                    <span>
                      {item.is_default ? "Базовый предмет" : `${item.price} монет`}
                    </span>
                  </div>
                </div>

                <p>{item.description}</p>

                <div className="shop-card__meta">
                  <span className="account-chip">
                    {item.active ? "Используется" : item.owned ? "Куплен" : "Не куплен"}
                  </span>
                </div>

                <button
                  type="button"
                  className={`button ${item.active ? "button--ghost" : "button--primary"}`}
                  onClick={() => void handleShopItemAction(item.id)}
                  disabled={item.active}
                >
                  {actionLabel}
                </button>
              </article>
            );
          })}
        </div>

        <div className="actions-row">
          <button className="button button--primary" onClick={() => setView("menu")}>
            В меню
          </button>
          <button className="button button--ghost" onClick={() => setView(currentRoute ? "difficulty" : "menu")}>
            К уровням
          </button>
        </div>
      </section>
    );
  }

  function renderAdminView() {
    if (!user?.is_admin) {
      return null;
    }

    return (
      <section className="card">
        <div className="card-badge">Управление контентом</div>
        <h2>Вопросы и маршруты</h2>
        <p className="card-text">
          Добавляйте и редактируйте задания для конкретных языков, сложностей и уровней.
        </p>

        <div className="admin-grid">
          <div className="admin-sidebar">
            <form className="admin-form" onSubmit={handleSaveQuestion}>
              <div className="admin-form__header">
                <h3>{editingQuestionId ? "Редактирование вопроса" : "Новый вопрос"}</h3>
                {editingQuestionId && (
                  <button
                    type="button"
                    className="button button--ghost"
                    onClick={() => resetDraftForm()}
                  >
                    Сбросить форму
                  </button>
                )}
              </div>

              <label className="field">
                <span>Маршрут</span>
                <select
                  value={draft.topic}
                  onChange={(event) => void handleAdminRouteChange(event.target.value)}
                >
                  {routes.map((route) => (
                    <option key={route.topic} value={route.topic}>
                      {route.language} • {route.difficulty_label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Тип вопроса</span>
                <select
                  value={draft.type}
                  onChange={(event) =>
                    setDraft((prev) => ({
                      ...prev,
                      type: event.target.value as "choice" | "input",
                    }))
                  }
                >
                  <option value="choice">choice</option>
                  <option value="input">input</option>
                </select>
              </label>

              <label className="field">
                <span>Порядок в маршруте</span>
                <input
                  value={draft.order_index}
                  onChange={(event) =>
                    setDraft((prev) => ({ ...prev, order_index: event.target.value }))
                  }
                />
              </label>

              <label className="field">
                <span>Текст вопроса</span>
                <textarea
                  value={draft.prompt}
                  onChange={(event) =>
                    setDraft((prev) => ({ ...prev, prompt: event.target.value }))
                  }
                />
              </label>

              <label className="field">
                <span>Подсказка / объяснение</span>
                <textarea
                  value={draft.explanation}
                  onChange={(event) =>
                    setDraft((prev) => ({ ...prev, explanation: event.target.value }))
                  }
                />
              </label>

              <label className="field">
                <span>Плейсхолдер для текстового ответа</span>
                <input
                  value={draft.placeholder}
                  onChange={(event) =>
                    setDraft((prev) => ({ ...prev, placeholder: event.target.value }))
                  }
                />
              </label>

              {draft.type === "choice" && (
                <label className="field">
                  <span>Варианты ответа, по одному в строке</span>
                  <textarea
                    value={draft.options_text}
                    onChange={(event) =>
                      setDraft((prev) => ({ ...prev, options_text: event.target.value }))
                    }
                  />
                </label>
              )}

              <label className="field">
                <span>
                  {draft.type === "choice"
                    ? "Правильный ответ"
                    : "Допустимые ответы, по одному в строке"}
                </span>
                <textarea
                  value={draft.answers_text}
                  onChange={(event) =>
                    setDraft((prev) => ({ ...prev, answers_text: event.target.value }))
                  }
                />
              </label>

              <button className="button button--primary" type="submit">
                {editingQuestionId ? "Сохранить вопрос" : "Добавить вопрос"}
              </button>
            </form>
          </div>

          <div className="admin-list-panel">
            <div className="admin-list__header">
              <div>
                <h3>{currentRoute ? getRouteTitle(currentRoute) : "Список вопросов"}</h3>
                <p className="card-text">
                  {currentRoute
                    ? `Показаны только вопросы маршрута ${getRouteTitle(currentRoute)}.`
                    : "Выбери маршрут слева, чтобы увидеть его вопросы."}
                </p>
              </div>
              {currentRoute && (
                <span className="account-chip">
                  Вопросов: {adminQuestions.length}
                </span>
              )}
            </div>

            <div className="admin-list">
              {adminQuestions.length === 0 ? (
                <div className="empty-state">Для этого маршрута пока нет вопросов.</div>
              ) : (
                adminQuestions.map((question) => (
                  <article
                    key={question.id}
                    className={`admin-question-row ${
                      selectedAdminQuestion?.id === question.id ? "admin-question-row--selected" : ""
                    }`}
                  >
                    <button
                      type="button"
                      className="admin-question-row__select"
                      onClick={() => setSelectedAdminQuestionId(question.id)}
                    >
                      <span className="pill">
                        Уровень {question.level_index + 1} • Задание {question.task_index + 1}
                      </span>
                      <strong className="admin-question-row__title">{question.prompt}</strong>
                    </button>

                    <div className="actions-row actions-row--compact">
                      <button
                        className="button button--ghost"
                        type="button"
                        onClick={() => beginEditQuestion(question)}
                      >
                        Редактировать
                      </button>
                      <button
                        className="button button--ghost button--danger"
                        type="button"
                        onClick={() => void handleDeleteQuestion(question.id)}
                      >
                        Удалить
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>

            {selectedAdminQuestion && (
              <article className="admin-question-detail">
                <div className="admin-question-detail__header">
                  <div>
                    <span className="pill">
                      Уровень {selectedAdminQuestion.level_index + 1} • Задание{" "}
                      {selectedAdminQuestion.task_index + 1}
                    </span>
                    <h3>{selectedAdminQuestion.prompt}</h3>
                  </div>
                </div>

                <p>{selectedAdminQuestion.explanation}</p>

                {selectedAdminQuestion.type === "choice" && (
                  <div className="list-block">
                    <strong>Варианты ответа:</strong>
                    <ul>
                      {selectedAdminQuestion.options.map((option) => (
                        <li key={option}>{option}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="list-block">
                  <strong>Правильные ответы:</strong>
                  <ul>
                    {selectedAdminQuestion.correct_answers.map((answer) => (
                      <li key={answer}>{answer}</li>
                    ))}
                  </ul>
                </div>
              </article>
            )}
          </div>
        </div>
      </section>
    );
  }

  return (
    <div className="app-shell">
      <div className="bg-orb bg-orb--one" />
      <div className="bg-orb bg-orb--two" />

      <main className="panel">
        <section className="hero-copy">
          <p className="eyebrow">{APP_TITLE} • Практика по программированию</p>
          <h1>Маршруты, уровни и прогресс в одном приложении</h1>
        </section>

        {renderTopNav()}
        {renderStatusBar()}

        {view === "auth" && renderAuthView()}
        {view === "menu" && renderMenuView()}
        {view === "difficulty" && renderDifficultyView()}
        {view === "quiz" && renderQuizView()}
        {view === "shop" && renderShopView()}
        {view === "account" && renderAccountView()}
        {view === "leaderboard" && renderLeaderboardView()}
        {view === "admin" && renderAdminView()}
        {view === "result" && renderResultView()}
      </main>
    </div>
  );
}

export default App;
