import { useEffect, useRef, useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import bolotoBackdrop from "../boloto.png";
import swampBackdrop from "../swamp_bg.png";
import winBackdrop from "../win.jpg";
import {
  createAppCopy,
  formatAppDate,
  formatAppTime,
  getHtmlLang,
  getStoredLocale,
  getStoredTheme,
  LOCALE_STORAGE_KEY,
  THEME_STORAGE_KEY,
  type AppLocale,
  type ThemeMode,
} from "./i18n";
import {
  ApiError,
  applySession,
  buyOrEquipShopItem,
  clearSessionContext,
  createAdminQuestion,
  createPromoCode,
  deleteAdminQuestion,
  deletePromoCode,
  downloadProgressReport,
  getAllProgress,
  getAdminQuestions,
  getAdminPromos,
  getBootstrap,
  getDailyChallenge,
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
  submitDailyChallenge,
  submitAnswer,
  updateProfile,
  updateAdminQuestion,
  updatePromoCode,
} from "./api";
import { FrogAvatar, FrogFamily, PrimitiveFrog } from "./components/FrogArt";
import { useRouteHearts } from "./hooks/useRouteHearts";
import {
  SOURCE_LOCALE,
  useAutoDocumentTitleTranslation,
  useAutoPageTranslation,
} from "./pageTranslator";
import type {
  AccountUpdatePayload,
  AdminQuestion,
  AdminQuestionPayload,
  AnswerResult,
  AuthResponse,
  Credentials,
  DailyChallengeResponse,
  DailyChallengeSubmitResponse,
  LeaderboardMetric,
  LeaderboardEntry,
  Progress,
  PromoCode,
  PromoCodePayload,
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
  | "daily"
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

type PromoDraftState = {
  code: string;
  description: string;
  reward_coins: string;
  unlock_all_levels: boolean;
  is_active: boolean;
};

const DEFAULT_TOPIC = "python-easy";
const HEARTS_PER_LEVEL = 3;
const QUESTION_TIMER_SECONDS = 20;
function createEmptyDraft(locale: AppLocale = "ru", topic = DEFAULT_TOPIC): QuestionDraft {
  const copy = createAppCopy(locale);

  return {
    topic,
    type: "choice",
    prompt: "",
    explanation: "",
    placeholder: "",
    order_index: "0",
    options_text: copy.admin.defaultOptionsText,
    answers_text: copy.admin.defaultAnswersText,
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

function createEmptyPromoDraft(): PromoDraftState {
  return {
    code: "",
    description: "",
    reward_coins: "0",
    unlock_all_levels: false,
    is_active: true,
  };
}

function normalizeWhitespace(value: string) {
  return value.trim().replace(/\s+/g, " ");
}

function formatDate(value: string | null, locale: AppLocale) {
  return formatAppDate(value, locale);
}

function formatTime(value: string | null, locale: AppLocale) {
  return formatAppTime(value, locale);
}

function getRouteTitle(route: RouteOption | null, routeNotSelectedLabel: string) {
  if (!route) {
    return routeNotSelectedLabel;
  }

  return `${route.language} • ${route.difficulty_label}`;
}

function getRouteTaskSummary(route: RouteOption, locale: AppLocale) {
  return createAppCopy(locale).formatTaskSummary(route.levels_total, route.tasks_per_level);
}

function getRouteContentHint(route: RouteOption, locale: AppLocale) {
  return getRouteTaskSummary(route, locale);
}

function getSceneStyle(theme: ThemeMode, backdrop: string, variant: "auth" | "menu" | "result") {
  const overlays: Record<ThemeMode, Record<typeof variant, string>> = {
    dark: {
      auth: "linear-gradient(180deg, rgba(8, 18, 14, 0.18), rgba(8, 18, 14, 0.74))",
      menu: "linear-gradient(180deg, rgba(8, 18, 14, 0.16), rgba(8, 18, 14, 0.76))",
      result: "linear-gradient(180deg, rgba(8, 18, 14, 0.12), rgba(8, 18, 14, 0.68))",
    },
    light: {
      auth: "linear-gradient(180deg, rgba(255, 255, 255, 0.24), rgba(241, 247, 243, 0.88))",
      menu: "linear-gradient(180deg, rgba(255, 255, 255, 0.22), rgba(237, 244, 239, 0.9))",
      result: "linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(232, 241, 235, 0.88))",
    },
  };

  return {
    backgroundImage: `${overlays[theme][variant]}, url(${backdrop})`,
  } satisfies CSSProperties;
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
  const [uiLocale, setUiLocale] = useState<AppLocale>(() => getStoredLocale());
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => getStoredTheme());
  const sourceLocale: AppLocale = SOURCE_LOCALE;
  const copy = createAppCopy(SOURCE_LOCALE);
  const sourcePageTitle = `${copy.appTitle} • ${copy.heroTitle}`;
  const appPanelRef = useRef<HTMLElement | null>(null);
  useAutoPageTranslation(appPanelRef, sourceLocale, uiLocale);
  useAutoDocumentTitleTranslation(sourcePageTitle, SOURCE_LOCALE, uiLocale);

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
    useState(createAppCopy(SOURCE_LOCALE).leaderboard.coins);
  const [leaderboardScope, setLeaderboardScope] = useState<"route" | "global">("global");
  const [shopItems, setShopItems] = useState<ShopItem[]>([]);
  const [adminQuestions, setAdminQuestions] = useState<AdminQuestion[]>([]);
  const [adminPromos, setAdminPromos] = useState<PromoCode[]>([]);
  const [selectedAdminQuestionId, setSelectedAdminQuestionId] = useState<number | null>(null);
  const [editingPromoCode, setEditingPromoCode] = useState<string | null>(null);

  const [authForm, setAuthForm] = useState<Credentials>({
    username: "",
    password: "",
  });
  const [accountForm, setAccountForm] = useState<AccountFormState>(() =>
    createEmptyAccountForm(),
  );
  const [promoCode, setPromoCode] = useState("");
  const [promoDraft, setPromoDraft] = useState<PromoDraftState>(() => createEmptyPromoDraft());

  const [selectedOption, setSelectedOption] = useState("");
  const [typedAnswer, setTypedAnswer] = useState("");
  const [feedback, setFeedback] = useState<AnswerResult | null>(null);
  const [feedbackAction, setFeedbackAction] = useState<FeedbackAction>(null);
  const [pendingProgress, setPendingProgress] = useState<Progress | null>(null);
  const [displayIndex, setDisplayIndex] = useState(0);
  const [timerEnabled, setTimerEnabled] = useState(false);
  const [timeLeft, setTimeLeft] = useState(QUESTION_TIMER_SECONDS);
  const [timedOutQuestionId, setTimedOutQuestionId] = useState<number | null>(null);
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
  const [dailyChallenge, setDailyChallenge] = useState<DailyChallengeResponse | null>(null);
  const [dailySelectedOption, setDailySelectedOption] = useState("");
  const [dailyTypedAnswer, setDailyTypedAnswer] = useState("");
  const [dailyResult, setDailyResult] = useState<DailyChallengeSubmitResponse | null>(null);

  const [draft, setDraft] = useState<QuestionDraft>(() => createEmptyDraft(SOURCE_LOCALE));
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);

  const [busyLabel, setBusyLabel] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const authSceneStyle = getSceneStyle(themeMode, bolotoBackdrop, "auth");
  const menuSceneStyle = getSceneStyle(themeMode, swampBackdrop, "menu");
  const resultSceneStyle = getSceneStyle(themeMode, winBackdrop, "result");

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

  useEffect(() => {
    const htmlRoot = document.documentElement;
    htmlRoot.dataset.theme = themeMode;
    htmlRoot.lang = getHtmlLang(uiLocale);
    htmlRoot.style.colorScheme = themeMode;
    window.localStorage.setItem(LOCALE_STORAGE_KEY, uiLocale);
    window.localStorage.setItem(THEME_STORAGE_KEY, themeMode);
  }, [themeMode, uiLocale]);

  useEffect(() => {
    if (!user) {
      return;
    }

    let active = true;

    async function refreshLocalizedContent() {
      try {
        const routeResponse = await getRoutes(uiLocale);
        if (!active) {
          return;
        }

        setRoutes(routeResponse.items);

        const localizedCurrentRoute =
          currentRoute
            ? routeResponse.items.find((route) => route.topic === currentRoute.topic) ?? currentRoute
            : null;

        if (localizedCurrentRoute) {
          setCurrentRoute(localizedCurrentRoute);

          if (view === "result") {
            setRoundResult((prev) =>
              prev
                ? {
                    ...prev,
                    routeTitle: getRouteTitle(localizedCurrentRoute, copy.common.routeNotSelected),
                  }
                : prev,
            );
          }
        }

        if (view === "quiz" && localizedCurrentRoute) {
          await loadRoute(localizedCurrentRoute, "quiz");
        } else if (view === "daily") {
          await openDailyChallenge();
        } else if (view === "leaderboard") {
          await refreshLeaderboard(localizedCurrentRoute?.topic, leaderboardMetric);
        } else if (view === "shop") {
          await openShop();
        } else if (view === "admin") {
          await openAdmin(localizedCurrentRoute?.topic ?? accountRouteTopic ?? routeResponse.items[0]?.topic);
        }
      } catch {
        // Keep the current content if the localized refresh fails.
      }
    }

    void refreshLocalizedContent();
    return () => {
      active = false;
    };
  }, [uiLocale]);

  useEffect(() => {
    if (leaderboardMetric === "coins") {
      setLeaderboardMetricLabel(copy.leaderboard.coins);
    }
  }, [copy.leaderboard.coins, leaderboardMetric]);

  useEffect(() => {
    if (view !== "quiz" || !timerEnabled || !currentQuestion || feedback !== null) {
      return;
    }

    setTimeLeft(QUESTION_TIMER_SECONDS);
    setTimedOutQuestionId(null);
  }, [view, timerEnabled, currentQuestion?.id]);

  useEffect(() => {
    if (view !== "quiz" || !timerEnabled || !currentQuestion || feedback !== null) {
      return;
    }

    if (timeLeft <= 0) {
      if (timedOutQuestionId !== currentQuestion.id) {
        setTimedOutQuestionId(currentQuestion.id);
        void handleTimedOutQuestion();
      }
      return;
    }

    const timerId = window.setTimeout(() => {
      setTimeLeft((prev) => prev - 1);
    }, 1000);

    return () => window.clearTimeout(timerId);
  }, [view, timerEnabled, currentQuestion?.id, feedback, timeLeft, timedOutQuestionId]);

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
    setTimedOutQuestionId(null);
    setTimeLeft(QUESTION_TIMER_SECONDS);
  }

  function resetDailyUi() {
    setDailySelectedOption("");
    setDailyTypedAnswer("");
    setDailyResult(null);
  }

  function resetDraftForm(topic = currentRoute?.topic ?? routes[0]?.topic ?? DEFAULT_TOPIC) {
    setDraft(createEmptyDraft(SOURCE_LOCALE, topic));
    setEditingQuestionId(null);
  }

  function resetPromoDraft() {
    setPromoDraft(createEmptyPromoDraft());
    setEditingPromoCode(null);
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
    setLeaderboardMetricLabel(copy.leaderboard.coins);
    setLeaderboardScope("global");
    setShopItems([]);
    setAdminQuestions([]);
    setAdminPromos([]);
    setEditingPromoCode(null);
    setPromoDraft(createEmptyPromoDraft());
    setRoundResult(null);
    resetHeartsState();
    setTimerEnabled(false);
    setTimeLeft(QUESTION_TIMER_SECONDS);
    setTimedOutQuestionId(null);
    setDailyChallenge(null);
    setDailySelectedOption("");
    setDailyTypedAnswer("");
    setDailyResult(null);
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

    setErrorMessage(copy.status.genericApiFailure);
  }

  async function hydrateSession(
    nextView: View = "menu",
    sessionResponse: AuthResponse | null = null,
    silentAuthFailure = false,
  ) {
    setBusyLabel(copy.status.loadingProfile);
    setErrorMessage("");

    try {
      const activeSession = sessionResponse ?? (await getSession());
      storeSession(activeSession);

      const [routeResponse, progressResponse] = await Promise.all([
        getRoutes(uiLocale),
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
          : createEmptyDraft(SOURCE_LOCALE, routeResponse.items[0]?.topic ?? DEFAULT_TOPIC),
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

    setBusyLabel(copy.status.loadingRoute);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const [bootstrap, leaderboardResponse] = await Promise.all([
        getBootstrap(route.topic, uiLocale),
        getLeaderboard(route.topic, leaderboardMetric, uiLocale),
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
    setBusyLabel(authMode === "login" ? copy.status.loggingIn : copy.status.creatingAccount);
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
          ? copy.auth.successLogin
          : copy.auth.successRegister(response.user.full_username),
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

    setBusyLabel(copy.status.loggingOut);
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

    const response = await getLeaderboard(
      topic,
      metricOverride ?? leaderboardMetric,
      uiLocale,
    );
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

    setBusyLabel(copy.status.loadingLeaderboard);
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

  async function openDailyChallenge() {
    if (!user) {
      return;
    }

    setBusyLabel(copy.status.loadingDaily);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const response = await getDailyChallenge(uiLocale);
      setDailyChallenge(response);
      resetDailyUi();
      setView("daily");
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

    setBusyLabel(copy.status.loadingAdmin);
    setErrorMessage("");

    try {
      const routeResponse = await getRoutes(uiLocale);
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

      const [data, promoResponse] = await Promise.all([
        getAdminQuestions(route.topic, uiLocale),
        getAdminPromos(uiLocale),
      ]);
      setRoutes(nextRoutes);
      setCurrentRoute(route);
      setSelectedLanguage(route.language);
      setAdminQuestions(data);
      setAdminPromos(promoResponse.items);
      setSelectedAdminQuestionId((prev) =>
        data.some((question) => question.id === prev) ? prev : (data[0]?.id ?? null),
      );
      setEditingPromoCode((prev) =>
        promoResponse.items.some((promo) => promo.code === prev) ? prev : null,
      );
      setDraft((prev) =>
        shouldResetForms || prev.topic !== route.topic
          ? createEmptyDraft(SOURCE_LOCALE, route.topic)
          : prev,
      );
      if (!promoResponse.items.some((promo) => promo.code === editingPromoCode)) {
        resetPromoDraft();
      }
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

    setBusyLabel(copy.status.loadingShop);
    setErrorMessage("");

    try {
      const response = await getShop(uiLocale);
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

  async function handleDownloadProgressReport() {
    if (!user) {
      return;
    }

    setBusyLabel(copy.status.preparingPdf);
    setErrorMessage("");

    try {
      const blob = await downloadProgressReport(uiLocale);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `froggy-progress-report-${uiLocale}-${user.id}.pdf`;
      document.body.append(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setSuccessMessage(copy.account.pdfReady);
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
      setErrorMessage(copy.status.profilePasswordMismatch);
      setSuccessMessage("");
      return;
    }

    if (currentPassword && !newPassword) {
      setErrorMessage(copy.status.profilePasswordMissing);
      setSuccessMessage("");
      return;
    }

    setBusyLabel(copy.status.savingProfile);
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
      setSuccessMessage(copy.account.profileSaved);

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
      setErrorMessage(copy.status.promoCodeEmpty);
      setSuccessMessage("");
      return;
    }

    setBusyLabel(copy.status.checkingPromo);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const payload: PromoRedeemPayload = { code };
      const response = await redeemPromoCode(payload, uiLocale);
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
      setSuccessMessage(response.message || copy.account.promoActivated);

      if (leaderboardMetric === "coins") {
        await refreshLeaderboard(undefined, "coins");
      }
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function handleDailyChallengeSubmit() {
    if (!dailyChallenge || dailyChallenge.already_answered || dailyResult) {
      return;
    }

    const answer =
      dailyChallenge.question.type === "choice" ? dailySelectedOption : dailyTypedAnswer;

    if (!answer.trim()) {
      setErrorMessage(copy.status.dailyAnswerEmpty);
      setSuccessMessage("");
      return;
    }

    setBusyLabel(copy.status.checkingDaily);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const response = await submitDailyChallenge({ answer }, uiLocale);
      setDailyResult(response);
      setDailyChallenge((prev) =>
        prev
          ? {
              ...prev,
              already_answered: true,
              result: {
                is_correct: response.is_correct,
                correct_answers: response.correct_answers,
                explanation: response.explanation,
                reward_coins: response.reward_coins,
                answered_at: response.answered_at,
              },
              leaderboard: response.leaderboard,
            }
          : prev,
      );
      setUser(response.user);
      if (response.is_correct) {
        setSuccessMessage(copy.daily.answerCorrect(response.reward_coins));
      } else {
        setSuccessMessage(copy.daily.answerSavedWrong);
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

    setBusyLabel(copy.status.updatingCatalog);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const response = await buyOrEquipShopItem(itemId, uiLocale);
      setUser(response.user);
      setShopItems(response.items);
      setSuccessMessage(response.message ?? copy.shop.catalogUpdated);

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

    setBusyLabel(copy.status.preparingLevel);
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

    setBusyLabel(copy.status.resettingRoute);
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

    const confirmed = window.confirm(copy.status.resetConfirm);
    if (!confirmed) {
      return;
    }

    setBusyLabel(copy.status.resettingAll);
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

      setSuccessMessage(copy.status.resetAllSuccess);
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function submitCurrentAnswer(answerOverride?: string, force = false) {
    if (!user || !currentRoute || !currentQuestion || (!force && !canSubmitAnswer)) {
      return;
    }

    setBusyLabel(copy.status.checkingAnswer);
    setErrorMessage("");

    try {
      const answerToSubmit = answerOverride ?? currentAnswer;
      const result = await submitAnswer({
        topic: currentRoute.topic,
        question_id: currentQuestion.id,
        answer: answerToSubmit,
      }, uiLocale);
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
            routeTitle: getRouteTitle(currentRoute, copy.common.routeNotSelected),
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

  async function handleSubmitAnswer() {
    await submitCurrentAnswer();
  }

  async function handleTimedOutQuestion() {
    if (!currentQuestion || feedback !== null) {
      return;
    }

    setErrorMessage(copy.status.timeOut);
    await submitCurrentAnswer(" ", true);
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
    setSuccessMessage(copy.admin.questionOpened);
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

  function buildPromoPayload(): PromoCodePayload {
    const rewardCoins = Number.parseInt(promoDraft.reward_coins || "0", 10);

    return {
      code: promoDraft.code.trim().toUpperCase(),
      description: normalizeWhitespace(promoDraft.description),
      reward_coins: Number.isNaN(rewardCoins) ? 0 : rewardCoins,
      unlock_all_levels: promoDraft.unlock_all_levels,
      is_active: promoDraft.is_active,
    };
  }

  function beginEditPromo(promo: PromoCode) {
    setEditingPromoCode(promo.code);
    setPromoDraft({
      code: promo.code,
      description: promo.description,
      reward_coins: String(promo.reward_coins),
      unlock_all_levels: promo.unlock_all_levels,
      is_active: promo.is_active,
    });
    setSuccessMessage(copy.admin.promoOpened);
    setErrorMessage("");
  }

  async function handleSaveQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user?.is_admin) {
      return;
    }

    setBusyLabel(editingQuestionId ? copy.status.savingQuestion : copy.status.addingQuestion);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const payload = buildPayloadFromDraft();

      if (editingQuestionId) {
        await updateAdminQuestion(editingQuestionId, payload);
        setSuccessMessage(copy.admin.questionSaved);
      } else {
        await createAdminQuestion(payload);
        setSuccessMessage(copy.admin.questionAdded);
      }

      resetDraftForm(payload.topic);
      await openAdmin(payload.topic);
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function handleSavePromo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user?.is_admin) {
      return;
    }

    setBusyLabel(editingPromoCode ? copy.status.savingPromo : copy.status.addingPromo);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const payload = buildPromoPayload();
      if (editingPromoCode) {
        await updatePromoCode(editingPromoCode, payload);
        setSuccessMessage(copy.admin.promoSaved);
      } else {
        await createPromoCode(payload);
        setSuccessMessage(copy.admin.promoAdded);
      }
      resetPromoDraft();
      await openAdmin(currentRoute?.topic);
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

    const confirmed = window.confirm(copy.status.deletingQuestion);
    if (!confirmed) {
      return;
    }

    setBusyLabel(copy.status.deletingQuestion);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      await deleteAdminQuestion(questionId);
      if (editingQuestionId === questionId) {
        resetDraftForm();
      }
      setSuccessMessage(copy.admin.questionDeleted);
      await openAdmin(draft.topic);
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function handleDeletePromo(code: string) {
    if (!user?.is_admin) {
      return;
    }

    const confirmed = window.confirm(copy.status.deletingPromo(code));
    if (!confirmed) {
      return;
    }

    setBusyLabel(copy.status.deletingPromo(code));
    setErrorMessage("");
    setSuccessMessage("");

    try {
      await deletePromoCode(code);
      if (editingPromoCode === code) {
        resetPromoDraft();
      }
      setSuccessMessage(copy.admin.promoDeleted);
      await openAdmin(currentRoute?.topic);
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  function getTopNavButtonClass(isActive: boolean) {
    return `button button--ghost${isActive ? " top-nav__button--active" : ""}`;
  }

  function renderSettingsBar() {
    return (
      <div className="settings-bar">
        <div className="settings-bar__group">
          <span className="settings-bar__label">{copy.settings.themeLabel}</span>
          <div className="settings-bar__toggle" role="group" aria-label={copy.settings.themeLabel}>
            {(["dark", "light"] as ThemeMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                className={`settings-bar__toggle-btn ${
                  themeMode === mode ? "settings-bar__toggle-btn--active" : ""
                }`}
                onClick={() => setThemeMode(mode)}
                aria-pressed={themeMode === mode}
              >
                {copy.settings.themeNames[mode]}
              </button>
            ))}
          </div>
        </div>

        <label className="settings-bar__group settings-bar__select">
          <span className="settings-bar__label">{copy.settings.languageLabel}</span>
          <select
            value={uiLocale}
            onChange={(event) => setUiLocale(event.target.value as AppLocale)}
            aria-label={copy.settings.languageLabel}
          >
            {copy.localeOrder.map((locale) => (
              <option key={locale} value={locale}>
                {copy.settings.localeNames[locale]}
              </option>
            ))}
          </select>
        </label>
      </div>
    );
  }

  function renderTopNav() {
    if (!user) {
      return null;
    }

    const isMenuActive = view === "menu";
    const isAccountActive = view === "account";
    const isLevelsActive = view === "difficulty" || view === "quiz" || view === "result";
    const isLeaderboardActive = view === "leaderboard";
    const isDailyActive = view === "daily";
    const isShopActive = view === "shop";
    const isAdminActive = view === "admin";

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
            <strong translate="no">{getUserHandle(user)}</strong>
            <span>
              {currentRoute
                ? `${copy.common.route}: ${getRouteTitle(currentRoute, copy.common.routeNotSelected)}`
                : copy.common.chooseLanguageAndDifficulty}
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
          <button
            className={getTopNavButtonClass(isMenuActive)}
            aria-current={isMenuActive ? "page" : undefined}
            onClick={() => setView("menu")}
          >
            {copy.common.home}
          </button>
          <button
            className={getTopNavButtonClass(isAccountActive)}
            aria-current={isAccountActive ? "page" : undefined}
            onClick={openAccount}
          >
            {copy.common.account}
          </button>
          <button
            className={getTopNavButtonClass(isLevelsActive)}
            aria-current={isLevelsActive ? "page" : undefined}
            onClick={() => setView(currentRoute ? "difficulty" : "menu")}
          >
            {copy.common.levels}
          </button>
          <button
            className={getTopNavButtonClass(isLeaderboardActive)}
            aria-current={isLeaderboardActive ? "page" : undefined}
            onClick={() => void openLeaderboard()}
          >
            {copy.common.leaderboard}
          </button>
          <button
            className={getTopNavButtonClass(isDailyActive)}
            aria-current={isDailyActive ? "page" : undefined}
            onClick={() => void openDailyChallenge()}
          >
            {copy.common.daily}
          </button>
          <button
            className={getTopNavButtonClass(isShopActive)}
            aria-current={isShopActive ? "page" : undefined}
            onClick={() => void openShop()}
          >
            {copy.common.shop}
          </button>
          {user.is_admin && (
            <button
              className={getTopNavButtonClass(isAdminActive)}
              aria-current={isAdminActive ? "page" : undefined}
              onClick={() => void openAdmin()}
            >
              {copy.common.admin}
            </button>
          )}
          <button className="button button--ghost" onClick={handleLogout}>
            {copy.common.logout}
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
          <div className="auth-overview" style={authSceneStyle}>
            <div className="auth-overview__glass">
              <div className="auth-overview__intro">
                <h2>{copy.auth.eyebrow}</h2>
                <p className="auth-overview__text">{copy.auth.intro}</p>
              </div>

              <div className="auth-benefits">
                <article className="auth-benefit">
                  <span className="auth-benefit__icon" aria-hidden="true">
                    🗺️
                  </span>
                  <div>
                    <strong>{copy.auth.benefitRoutesTitle}</strong>
                    <p>{copy.auth.benefitRoutesText}</p>
                  </div>
                </article>

                <article className="auth-benefit">
                  <span className="auth-benefit__icon" aria-hidden="true">
                    💾
                  </span>
                  <div>
                    <strong>{copy.auth.benefitProgressTitle}</strong>
                    <p>{copy.auth.benefitProgressText}</p>
                  </div>
                </article>

                <article className="auth-benefit">
                  <span className="auth-benefit__icon" aria-hidden="true">
                    🏆
                  </span>
                  <div>
                    <strong>{copy.auth.benefitRewardsTitle}</strong>
                    <p>{copy.auth.benefitRewardsText}</p>
                  </div>
                </article>
              </div>
            </div>
          </div>

          <div className="auth-form-card">
            <div className="auth-form-card__header">
              <div>
                <p className="auth-kicker">
                  {authMode === "register" ? copy.auth.registerKicker : copy.auth.welcomeBack}
                </p>
                <h3>
                  {authMode === "register" ? copy.auth.registerTitle : copy.auth.loginTitle}
                </h3>
              </div>
              <span className="auth-form-card__emoji" aria-hidden="true">
                🐸
              </span>
            </div>

            <p className="auth-form-card__text">
              {authMode === "register" ? copy.auth.registerText : copy.auth.loginText}
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
                  {copy.auth.registerTab}
                </button>
                <button
                  type="button"
                  className={`auth-switch__btn ${
                    authMode === "login" ? "auth-switch__btn--active" : ""
                  }`}
                  onClick={() => setAuthMode("login")}
                >
                  {copy.auth.loginTab}
                </button>
              </div>

              <label className="field field--auth">
                <span>
                  {authMode === "login"
                    ? copy.auth.usernameLabelLogin
                    : copy.auth.usernameLabelRegister}
                </span>
                <input
                  value={authForm.username}
                  onChange={(event) =>
                    setAuthForm((prev) => ({ ...prev, username: event.target.value }))
                  }
                  placeholder={
                    authMode === "login"
                      ? copy.auth.usernamePlaceholderLogin
                      : copy.auth.usernamePlaceholderRegister
                  }
                />
              </label>

              <label className="field field--auth">
                <span>{copy.auth.passwordLabel}</span>
                <input
                  type="password"
                  value={authForm.password}
                  onChange={(event) =>
                    setAuthForm((prev) => ({ ...prev, password: event.target.value }))
                  }
                  placeholder={copy.auth.passwordPlaceholder}
                />
              </label>

              <button className="button button--primary" type="submit">
                {authMode === "login" ? copy.auth.submitLogin : copy.auth.submitRegister}
              </button>
            </form>

            <div className="auth-footnote">
              <span>{copy.auth.footnoteLanguages}</span>
              <span>{copy.auth.footnoteDifficulty}</span>
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
            <div className="card-badge">{copy.menu.badge}</div>
            <h2>{copy.menu.title}</h2>
            <p className="card-text">{copy.menu.intro}</p>

            <div className="stats-row">
              <article className="stat-box">
                <span className="stat-label">{copy.menu.languagesLabel}</span>
                <strong>{languageOptions.length}</strong>
              </article>

              <article className="stat-box">
                <span className="stat-label">{copy.menu.routesLabel}</span>
                <strong>{routes.length}</strong>
              </article>

              <article className="stat-box">
                <span className="stat-label">{copy.menu.walletLabel}</span>
                <strong>{currentCoins}</strong>
              </article>
            </div>
          </div>

          <div className="scene-art" style={menuSceneStyle}>
            <div className="frog-bubble">
              {copy.menu.bubble}
            </div>

            <div className="preview-panel">
              <h3>{copy.menu.previewTitle}</h3>
              <p>{copy.menu.previewText}</p>
            </div>

            <FrogFamily />

            <p className="scene-caption">
              {copy.menu.currentRoutePrefix}{" "}
              {currentRoute
                ? getRouteTitle(currentRoute, copy.common.routeNotSelected)
                : copy.common.routeNotSelected}
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
              <span className="route-card__eyebrow">{copy.settings.languageLabel}</span>
              <strong>{language}</strong>
              <span>
                {copy.menu.routeCount(
                  routes.filter((route) => route.language === language).length,
                )}
              </span>
            </button>
          ))}
        </div>

        <div className="actions-row">
          <button className="button button--ghost" onClick={openAccount}>
            {copy.menu.account}
          </button>
          <button className="button button--ghost" onClick={() => void openDailyChallenge()}>
            {copy.menu.daily}
          </button>
          <button className="button button--ghost" onClick={() => void openShop()}>
            {copy.menu.shop}
          </button>
          <button className="button button--ghost" onClick={() => void openLeaderboard()}>
            {copy.menu.leaderboard}
          </button>
          <button
            className="button button--ghost button--danger"
            onClick={() => void handleResetAllProgress()}
          >
            {copy.menu.resetAll}
          </button>
          <span className="account-chip">{copy.menu.currentRuns(currentRuns)}</span>
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
        <div className="card-badge">{copy.difficulty.badge}</div>
        <h2>{copy.difficulty.title(selectedLanguage)}</h2>
        <p className="card-text">{copy.difficulty.intro}</p>

        <div className="route-grid">
          {difficultyOptions.map((route) => {
            const savedProgress = routeProgressCache[route.topic];
            const isActiveRoute = activeRoute?.topic === route.topic;
            return (
              <article key={route.topic} className="route-card route-card--panel">
                <span className="route-card__eyebrow">{route.language}</span>
                <strong>{route.difficulty_label}</strong>
                <span>
                  {route.questions_total}{" "}
                  {copy.common.tasksLabel}
                </span>
                <span>{getRouteContentHint(route, SOURCE_LOCALE)}</span>
                <span>
                  {savedProgress
                    ? copy.difficulty.openedLevel(savedProgress.unlocked_level_index + 1)
                    : copy.difficulty.notStarted}
                </span>

                <button
                  className="button button--primary"
                  type="button"
                  onClick={() => void chooseDifficulty(route)}
                >
                  {isActiveRoute ? copy.difficulty.refreshRoute : copy.difficulty.openRoute}
                </button>
              </article>
            );
          })}
        </div>

        {activeRoute && activeProgress && hasActiveQuestions && (
          <>
            <div className="card-badge">{copy.difficulty.levelsBadge}</div>
            <h3>{getRouteTitle(activeRoute, copy.common.routeNotSelected)}</h3>
            <p className="card-text">
              {copy.difficulty.currentLevel(
                activeProgress.current_level_index + 1,
                activeProgress.current_task_index + 1,
                activeProgress.tasks_per_level,
              )}
            </p>

            <div className="map-summary">
              <span className="account-chip">
                {copy.difficulty.unlockedLevel(activeProgress.unlocked_level_index + 1)}
              </span>
              <span className="account-chip">
                {copy.difficulty.completedRuns}: {activeProgress.completed_runs}
              </span>
              <span className="account-chip">
                {copy.difficulty.bestScore}: {activeProgress.best_score}
              </span>
              <span className="account-chip">
                {copy.difficulty.coins}: {user?.coins ?? 0}
              </span>
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
                  ? copy.difficulty.currentTask(
                      activeProgress.current_task_index + 1,
                      activeProgress.tasks_per_level,
                    )
                  : isUnlocked
                    ? isReplayable
                      ? copy.difficulty.repeatAvailable
                      : copy.difficulty.available
                    : copy.difficulty.unavailable;
                const buttonText =
                  levelIndex === activeProgress.current_level_index &&
                  activeProgress.current_task_index > 0
                    ? copy.difficulty.continueLevel
                    : isReplayable
                      ? copy.difficulty.replayLevel
                      : copy.difficulty.startLevel;

                return (
                  <article key={levelIndex} className={`map-node ${statusClass}`}>
                    <div className="map-node__circle">{levelIndex + 1}</div>
                    <strong>
                      {copy.quiz.level(levelIndex + 1)}
                    </strong>
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
                        {copy.difficulty.unavailable}
                      </button>
                    )}
                  </article>
                );
              })}
            </div>

            <div className="actions-row">
              <button className="button button--ghost" onClick={() => setView("menu")}>
                {copy.difficulty.backToLanguages}
              </button>
              <button
                className="button button--ghost"
                onClick={() => void resetCurrentRoute(false)}
              >
                {copy.difficulty.resetRouteProgress}
              </button>
            </div>
          </>
        )}

        {activeRoute && activeProgress && !hasActiveQuestions && (
          <>
            <div className="card-badge">{copy.difficulty.levelsBadge}</div>
            <h3>{getRouteTitle(activeRoute, copy.common.routeNotSelected)}</h3>
            <div className="empty-state">
              {copy.difficulty.noTasksText}
            </div>

            <div className="actions-row">
              <button className="button button--ghost" onClick={() => setView("menu")}>
                {copy.difficulty.backToLanguages}
              </button>
              {user?.is_admin && (
                <button
                  className="button button--primary"
                  onClick={() => void openAdmin(activeRoute.topic)}
                >
                  {copy.difficulty.openAdmin}
                </button>
              )}
            </div>
          </>
        )}

        {!activeRoute && (
          <div className="actions-row">
            <button className="button button--ghost" onClick={() => setView("menu")}>
              {copy.difficulty.backToLanguages}
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
        : currentQuestion.placeholder?.trim() || copy.quiz.hintUnavailable;
    const actionLabel =
      feedback === null
        ? copy.quiz.checkAnswer
        : feedback.quiz_completed
          ? copy.quiz.toResults
          : feedbackAction === "level-reset"
            ? copy.quiz.restartLevel
            : feedbackAction === "advance"
              ? copy.quiz.nextTask
              : copy.quiz.retry;
    const timedOut = feedback !== null && timedOutQuestionId === currentQuestion.id;

    return (
      <section className="card card--quiz">
        <div className="quiz-topbar">
          <div>
            <p className="eyebrow">{getRouteTitle(currentRoute, copy.common.routeNotSelected)}</p>
            <h2>{copy.quiz.level(currentQuestion.level_index + 1)}</h2>
          </div>

          <div className="quiz-meta">
            <span>{copy.quiz.task(currentQuestion.task_index + 1, progress.tasks_per_level)}</span>
            <span>{copy.quiz.progressOpened(progress.current_score)}</span>
            <span>
              {timerEnabled ? (
                <>
                  {copy.quiz.onTime}
                  <span translate="no">{timeLeft}</span>
                  {copy.common.secondsShort}
                </>
              ) : (
                copy.quiz.timerOff
              )}
            </span>
          </div>
        </div>

        <div className="quiz-strip">
          <div className="task-dots" aria-label={copy.quiz.progressAria}>
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

          <div className="hearts-bar" aria-label={copy.quiz.heartsAria}>
            {heartsLeft.map((isAlive, index) => (
              <span key={index} className={isAlive ? "heart heart--alive" : "heart"}>
                {isAlive ? "❤️" : "🖤"}
              </span>
            ))}
          </div>
        </div>

        <div className="question-box">
          <p className="question-number">{copy.quiz.routeTask}</p>
          <h3>{currentQuestion.prompt}</h3>
        </div>

        <div className="hint-panel">
          <div className="actions-row actions-row--compact">
            <button
              className="button button--ghost"
              type="button"
              onClick={() => setShowHint((prev) => !prev)}
            >
              {showHint ? copy.quiz.hideHint : copy.quiz.showHint}
            </button>

            <button
              className="button button--ghost"
              type="button"
              onClick={() => setTimerEnabled((prev) => !prev)}
            >
              {timerEnabled ? copy.quiz.disableTimer : copy.quiz.enableTimer(QUESTION_TIMER_SECONDS)}
            </button>
          </div>

          {timerEnabled && (
            <div className="timer-panel">
              <div className="timer-panel__header">
                <strong>{copy.quiz.timedMode}</strong>
                <span>
                  {timeLeft} {copy.common.secondsShort}
                </span>
              </div>
              <div className="timer-panel__track" aria-hidden="true">
                <div
                  className="timer-panel__fill"
                  style={{
                    width: `${Math.max(0, (timeLeft / QUESTION_TIMER_SECONDS) * 100)}%`,
                  }}
                />
              </div>
              <p>{copy.quiz.timerAutoSubmit}</p>
            </div>
          )}

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
                feedback && isSelected && !feedback.is_correct ? "option-card--wrong" : "",
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
            <span>{copy.quiz.answer}</span>
              <input
                value={typedAnswer}
                placeholder={currentQuestion.placeholder ?? copy.quiz.answer}
                onChange={(event) => setTypedAnswer(event.target.value)}
                autoCapitalize="none"
                autoComplete="off"
                autoCorrect="off"
                spellCheck={false}
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
                ? copy.quiz.answerCorrect(feedback.coins_awarded)
                : timedOut && feedbackAction === "level-reset"
                  ? copy.quiz.levelResetTimeOut
                  : timedOut
                    ? copy.quiz.timeOutHearts(hearts)
                    : feedbackAction === "level-reset"
                      ? copy.quiz.levelReset
                      : copy.quiz.answerWrong(hearts)}
            </strong>
            {!feedback.is_correct && (
              <span>
                {copy.quiz.correctAnswerPrefix} {feedback.correct_answers.join(` ${copy.common.or} `)}
              </span>
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
            {copy.quiz.backToLevels}
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
            <div className="card-badge">{copy.result.badge}</div>
            <h2>{copy.result.title(roundResult.routeTitle)}</h2>
            <p className="score-line">
              {copy.result.scoreLine(roundResult.finalScore, roundResult.totalQuestions)}
            </p>
            <p className="card-text">
              {copy.result.bestScore(roundResult.bestScore)} {copy.result.completedRuns(roundResult.completedRuns)}
            </p>

            <div className="result-ring">
              <span>100%</span>
            </div>

            <div className="actions-row">
              <button
                className="button button--primary"
                onClick={() => void resetCurrentRoute(true)}
              >
                {copy.result.playAgain}
              </button>
              <button className="button button--ghost" onClick={() => setView("difficulty")}>
                {copy.result.toLevels}
              </button>
              <button
                className="button button--ghost"
                onClick={() => void openLeaderboard(currentRoute.topic)}
              >
                {copy.result.leaders}
              </button>
            </div>
          </div>

          <div className="scene-art" style={resultSceneStyle}>
            <div className="frog-bubble frog-bubble--result">
              {copy.result.bubble}
            </div>

            <div className="preview-panel">
              <h3>{copy.result.previewTitle}</h3>
              <p>{copy.result.previewText}</p>
            </div>

            <FrogFamily />

            <p className="scene-caption">{copy.result.caption}</p>
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
    const routeLabel = trackedRoute
      ? getRouteTitle(trackedRoute, copy.common.routeNotSelected)
      : copy.common.routeNotSelected;
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
          <div className="account-hero" style={menuSceneStyle}>
            <div className="account-hero__content">
              <div className="account-hero__topline">
                <FrogAvatar
                  accessory={user.active_skin}
                  className="account-avatar"
                  frogClassName="account-avatar__frog"
                  frogSize={62}
                />

                <div>
                  <p className="account-kicker">{copy.account.badge}</p>
                  <h2 translate="no">{loginPreview}</h2>
                  <p className="account-subtitle">{copy.account.subtitle}</p>
                </div>
              </div>

              <div className="account-rankline">
                <span className="account-chip">
                  {copy.account.tagLabel}: #{user.tag ?? "----"}
                </span>
                <span className="account-chip">
                  {copy.account.routeLabel}: {routeLabel}
                </span>
                <span className="account-chip">
                  {copy.account.skinLabel}: {user.active_skin_icon} {user.active_skin_label}
                </span>
                <span className="account-chip">
                  {copy.account.coinsLabel}: {user.coins}
                </span>
              </div>
            </div>
          </div>

          <div className="account-grid">
            <div className="account-panel">
              <div className="account-panel__header">
                <div>
                  <p className="account-panel__eyebrow">{copy.account.badge}</p>
                  <h3>{copy.account.settingsTitle}</h3>
                </div>
                <span className="account-progress-badge">
                  {copy.account.loginBadge(loginPreview)}
                </span>
              </div>

              <form className="account-form" onSubmit={handleAccountSubmit}>
                <label className="field">
                  <span>{copy.account.usernameLabel}</span>
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
                    <span>{copy.account.tagLabel}</span>
                    <strong>#{user.tag ?? "----"}</strong>
                  </div>
                  <div className="account-readonly">
                    <span>{copy.account.loginLabel}</span>
                    <strong translate="no">{loginPreview}</strong>
                  </div>
                </div>

                <p className="account-form__hint">{copy.account.tagHint}</p>

                <div className="account-form__grid">
                  <label className="field">
                    <span>{copy.account.currentPassword}</span>
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
                      placeholder={copy.account.currentPasswordPlaceholder}
                    />
                  </label>

                <label className="field">
                  <span>{copy.account.newPassword}</span>
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
                    placeholder={copy.auth.passwordPlaceholder}
                  />
                </label>
              </div>

                <label className="field">
                  <span>{copy.account.repeatNewPassword}</span>
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
                    placeholder={copy.account.repeatNewPassword}
                  />
                </label>

                <p className="account-form__hint">{copy.account.passwordHint}</p>

                <div className="account-actions">
                  <button className="button button--primary" type="submit">
                    {copy.account.saveChanges}
                  </button>
                  <button
                    className="button button--ghost"
                    type="button"
                    onClick={() => resetAccountForm(user)}
                  >
                    {copy.account.resetChanges}
                  </button>
                </div>
              </form>

              <div className="account-note">
                <span className="account-note__icon" aria-hidden="true">
                  🔐
                </span>
                <div>
                  <strong>{copy.account.loginAfterChangeTitle}</strong>
                  <p>{copy.account.loginAfterChangeText(loginPreview)}</p>
                </div>
              </div>

            </div>

            <div className="account-side-stack">
              <div className="account-panel">
                <div className="account-panel__header">
                  <div>
                    <p className="account-panel__eyebrow">{copy.account.progressTitle}</p>
                    <h3>{copy.account.progressTitle}</h3>
                  </div>
                  <span className="account-progress-badge">
                    {trackedRoute
                      ? copy.account.progressBadgeSelected
                      : copy.account.progressBadgeEmpty}
                  </span>
                </div>

                <label className="field">
                  <span>{copy.account.routeForProgress}</span>
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
                        ? copy.account.openedTasks(
                            openedQuestions,
                            trackedProgress.total_questions,
                          )
                        : copy.account.progressEmpty}
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
                    <span className="account-metric__label">{copy.account.bestScore}</span>
                    <strong>{trackedProgress?.best_score ?? 0}</strong>
                  </article>
                  <article className="account-metric">
                    <span className="account-metric__label">{copy.account.runs}</span>
                    <strong>{trackedProgress?.completed_runs ?? 0}</strong>
                  </article>
                  <article className="account-metric">
                    <span className="account-metric__label">{copy.account.unlockedLevel}</span>
                    <strong>{trackedProgress ? trackedProgress.unlocked_level_index + 1 : 1}</strong>
                  </article>
                </div>

                <div className="actions-row">
                  <button
                    className="button button--primary"
                    onClick={() => void openAccountRoute(trackedRoute)}
                  >
                    {copy.account.openRoute}
                  </button>
                  <button
                    className="button button--ghost"
                    onClick={() => void handleDownloadProgressReport()}
                  >
                    {copy.account.downloadPdf}
                  </button>
                  <button className="button button--ghost" onClick={() => void openShop()}>
                    {copy.account.shop}
                  </button>
                </div>
              </div>

              <div className="account-panel">
                <div className="account-panel__header">
                  <div>
                    <p className="account-panel__eyebrow">{copy.account.promoBadge}</p>
                    <h3>{copy.account.promoTitle}</h3>
                  </div>
                  <span className="account-progress-badge">{copy.account.promoBadge}</span>
                </div>

                <form className="account-form" onSubmit={handlePromoSubmit}>
                  <label className="field">
                    <span>{copy.account.promoCode}</span>
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

                  <p className="account-form__hint">{copy.account.promoHint}</p>

                  <button className="button button--primary" type="submit">
                    {copy.account.activatePromo}
                  </button>
                </form>
              </div>
            </div>
          </div>
        </div>
      </section>
    );
  }

  function renderDailyView() {
    if (!dailyChallenge) {
      return null;
    }

    const result = dailyResult ?? dailyChallenge.result;
    const question = dailyChallenge.question;
    const currentDailyAnswer =
      question.type === "choice" ? dailySelectedOption : dailyTypedAnswer;
    const canSubmitDaily =
      !dailyChallenge.already_answered &&
      !dailyResult &&
      currentDailyAnswer.trim().length > 0 &&
      busyLabel.length === 0;

    return (
      <section className="card">
        <div className="scene-layout">
          <div className="scene-copy">
            <div className="card-badge">{copy.daily.badge}</div>
            <h2>
              {copy.daily.titlePrefix} {dailyChallenge.challenge_date}
            </h2>
            <p className="card-text">{copy.daily.subtitle(dailyChallenge.reward_coins)}</p>

            <div className="map-summary">
              <span className="account-chip">
                {copy.daily.dateLabel}: {dailyChallenge.challenge_date}
              </span>
              <span className="account-chip">
                {copy.daily.statusLabel}:{" "}
                {dailyChallenge.already_answered
                  ? copy.daily.answeredLabel
                  : copy.daily.pendingLabel}
              </span>
              <span className="account-chip">
                {copy.account.coinsLabel}: {user?.coins ?? 0}
              </span>
            </div>

            <div className="question-box">
              <p className="question-number">{copy.daily.questionLabel}</p>
              <h3>{question.prompt}</h3>
            </div>

            {question.type === "choice" ? (
              <div className="options-grid">
                {question.options.map((option) => {
                  const isSelected = dailySelectedOption === option;
                  const isCorrectOption = result?.correct_answers.includes(option);
                  const classes = [
                    "option-card",
                    isSelected ? "option-card--selected" : "",
                    result && isCorrectOption ? "option-card--correct" : "",
                    result && isSelected && !result.is_correct ? "option-card--wrong" : "",
                  ]
                    .filter(Boolean)
                    .join(" ");

                  return (
                    <button
                      key={option}
                      type="button"
                      className={classes}
                      disabled={dailyChallenge.already_answered}
                      onClick={() => setDailySelectedOption(option)}
                    >
                      <span className="option-marker" />
                      <span>{option}</span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <label className="field">
                <span>{copy.quiz.answer}</span>
                <input
                  value={dailyTypedAnswer}
                  placeholder={question.placeholder ?? copy.daily.submitHint}
                  onChange={(event) => setDailyTypedAnswer(event.target.value)}
                  autoCapitalize="none"
                  autoComplete="off"
                  autoCorrect="off"
                  spellCheck={false}
                  disabled={dailyChallenge.already_answered}
                />
              </label>
            )}

            {result && (
              <div
                className={`status-box ${
                  result.is_correct ? "status-box--success" : "status-box--warning"
                }`}
              >
                <strong>
                  {result.is_correct
                    ? copy.daily.answerCorrect(result.reward_coins)
                    : copy.daily.answerSavedWrong}
                </strong>
                <span>
                  {copy.daily.correctAnswerPrefix} {result.correct_answers.join(` ${copy.common.or} `)}
                </span>
                <span>
                  {copy.daily.explanationPrefix} {result.explanation}
                </span>
                <span>
                  {copy.daily.answeredAtPrefix} {formatDate(result.answered_at, uiLocale)}
                </span>
              </div>
            )}

            {!dailyChallenge.already_answered && (
              <div className="actions-row">
                <button
                  className="button button--primary"
                  onClick={() => void handleDailyChallengeSubmit()}
                  disabled={!canSubmitDaily}
                >
                  {copy.daily.answerButton}
                </button>
                <button className="button button--ghost" onClick={() => setView("menu")}>
                  {copy.daily.laterButton}
                </button>
              </div>
            )}

            {dailyChallenge.already_answered && (
              <div className="actions-row">
                <button className="button button--primary" onClick={() => setView("menu")}>
                  {copy.daily.menuButton}
                </button>
                <button className="button button--ghost" onClick={openAccount}>
                  {copy.daily.accountButton}
                </button>
              </div>
            )}
          </div>

          <div className="scene-art" style={authSceneStyle}>
            <div className="frog-bubble">
              {copy.daily.bubble}
            </div>

            <div className="preview-panel">
              <h3>{copy.daily.leaderboardTitle}</h3>
              {dailyChallenge.leaderboard.length === 0 ? (
                <p>{copy.daily.leaderboardEmpty}</p>
              ) : (
                <ol className="leaderboard-mini">
                  {dailyChallenge.leaderboard.map((entry) => (
                    <li key={`${entry.rank}-${entry.full_username}`}>
                      <em>#{entry.rank}</em>
                      <span translate="no">{entry.full_username}</span>
                      <strong className="leaderboard-mini__time">
                        {formatTime(entry.answered_at, uiLocale)}
                      </strong>
                    </li>
                  ))}
                </ol>
              )}
            </div>

            <div className="daily-note">
              <strong>{copy.daily.howItWorksTitle}</strong>
              <p>{copy.daily.howItWorksText}</p>
            </div>
          </div>
        </div>
      </section>
    );
  }

  function renderLeaderboardView() {
    const routeLabel = currentRoute
      ? getRouteTitle(currentRoute, copy.common.routeNotSelected)
      : copy.common.routeNotSelected;
    const scopeText =
      leaderboardScope === "global"
        ? copy.leaderboard.globalScope
        : copy.leaderboard.routeScope(routeLabel);

    return (
      <section className="card">
        <div className="card-badge">{copy.leaderboard.badge}</div>
        <h2>
          {copy.leaderboard.titlePrefix} {leaderboardMetricLabel}
        </h2>
        <p className="card-text">{scopeText}</p>

        <div className="leaderboard-toolbar">
          <div className="map-summary">
            <span className="account-chip">
              {leaderboardScope === "global" ? copy.leaderboard.allRoutes : routeLabel}
            </span>
            <span className="account-chip">
              {copy.leaderboard.coins}: {user?.coins ?? 0}
            </span>
          </div>
        </div>

        {leaderboard.length === 0 ? (
          <div className="empty-state">
            {copy.leaderboard.emptyState}
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
                  <strong translate="no">{getLeaderboardHandle(entry)}</strong>
                  <span>
                    {copy.leaderboard.lastPlayed} {formatDate(entry.last_played_at, uiLocale)}
                  </span>
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
            {copy.leaderboard.back}
          </button>
          <button className="button button--ghost" onClick={() => void refreshLeaderboard()}>
            {copy.leaderboard.refresh}
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
            <div className="card-badge">{copy.shop.badge}</div>
            <h2>{copy.shop.title}</h2>
            <p className="card-text">{copy.shop.intro}</p>

            <div className="stats-row">
              <article className="stat-box">
                <span className="stat-label">{copy.shop.coinsLabel}</span>
                <strong>{user?.coins ?? 0}</strong>
              </article>

              <article className="stat-box">
                <span className="stat-label">{copy.shop.ownedLabel}</span>
                <strong>{ownedCount}</strong>
              </article>

              <article className="stat-box">
                <span className="stat-label">{copy.shop.skinLabel}</span>
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

          <div className="scene-art" style={menuSceneStyle}>
            <div className="frog-bubble">
              {copy.shop.activeItem}
            </div>

            <div className="preview-panel">
              <h3>{copy.shop.howEarnTitle}</h3>
              <p>{copy.shop.howEarnText}</p>
            </div>

            <FrogFamily />
          </div>
        </div>

        <div className="shop-grid">
          {shopItems.map((item) => {
            const actionLabel = item.active
              ? copy.common.used
              : item.owned
                ? copy.common.use
                : copy.shop.buyFor(item.price);

            return (
              <article key={item.id} className={`shop-card ${item.active ? "shop-card--active" : ""}`}>
                <div className="shop-card__head">
                  <span className="shop-card__icon" aria-hidden="true">
                    {item.icon}
                  </span>
                  <div>
                    <strong>{item.name}</strong>
                    <span>
                      {item.is_default
                        ? copy.shop.baseItem
                        : `${item.price} ${copy.account.coinsLabel}`}
                    </span>
                  </div>
                </div>

                <p>{item.description}</p>

                <div className="shop-card__meta">
                  <span className="account-chip">
                    {item.active ? copy.common.used : item.owned ? copy.common.bought : copy.common.notBought}
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
            {copy.shop.menu}
          </button>
          <button className="button button--ghost" onClick={() => setView(currentRoute ? "difficulty" : "menu")}>
            {copy.shop.levels}
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
        <div className="card-badge">{copy.admin.badge}</div>
        <h2>{copy.admin.title}</h2>
        <p className="card-text">{copy.admin.intro}</p>

        <div className="admin-grid">
          <div className="admin-sidebar">
            <form className="admin-form" onSubmit={handleSaveQuestion}>
              <div className="admin-form__header">
                <h3>{editingQuestionId ? copy.admin.editQuestionTitle : copy.admin.newQuestionTitle}</h3>
                {editingQuestionId && (
                  <button
                    type="button"
                    className="button button--ghost"
                    onClick={() => resetDraftForm()}
                  >
                    {copy.admin.resetForm}
                  </button>
                )}
              </div>

              <label className="field">
                <span>{copy.admin.routeLabel}</span>
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
                <span>{copy.admin.questionType}</span>
                <select
                  value={draft.type}
                  onChange={(event) =>
                    setDraft((prev) => ({
                      ...prev,
                      type: event.target.value as "choice" | "input",
                    }))
                  }
                >
                  <option value="choice">{copy.common.choiceType}</option>
                  <option value="input">{copy.common.inputType}</option>
                </select>
              </label>

              <label className="field">
                <span>{copy.admin.orderIndex}</span>
                <input
                  value={draft.order_index}
                  onChange={(event) =>
                    setDraft((prev) => ({ ...prev, order_index: event.target.value }))
                  }
                />
              </label>

              <label className="field">
                <span>{copy.admin.questionText}</span>
                <textarea
                  value={draft.prompt}
                  onChange={(event) =>
                    setDraft((prev) => ({ ...prev, prompt: event.target.value }))
                  }
                />
              </label>

              <label className="field">
                <span>{copy.admin.hintExplanation}</span>
                <textarea
                  value={draft.explanation}
                  onChange={(event) =>
                    setDraft((prev) => ({ ...prev, explanation: event.target.value }))
                  }
                />
              </label>

              <label className="field">
                <span>{copy.admin.placeholder}</span>
                <input
                  value={draft.placeholder}
                  onChange={(event) =>
                    setDraft((prev) => ({ ...prev, placeholder: event.target.value }))
                  }
                />
              </label>

              {draft.type === "choice" && (
                <label className="field">
                  <span>{copy.admin.optionsLabel}</span>
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
                    ? copy.admin.correctAnswerChoiceLabel
                    : copy.admin.correctAnswerInputLabel}
                </span>
                <textarea
                  value={draft.answers_text}
                  onChange={(event) =>
                    setDraft((prev) => ({ ...prev, answers_text: event.target.value }))
                  }
                />
              </label>

              <button className="button button--primary" type="submit">
                {editingQuestionId ? copy.admin.saveQuestion : copy.admin.addQuestion}
              </button>
            </form>

            <form className="admin-form" onSubmit={handleSavePromo}>
              <div className="admin-form__header">
                <h3>{editingPromoCode ? copy.admin.editPromoTitle : copy.admin.newPromoTitle}</h3>
                {editingPromoCode && (
                  <button
                    type="button"
                    className="button button--ghost"
                    onClick={() => resetPromoDraft()}
                  >
                    {copy.admin.resetForm}
                  </button>
                )}
              </div>

              <label className="field">
                <span>{copy.admin.codeLabel}</span>
                <input
                  value={promoDraft.code}
                  onChange={(event) =>
                    setPromoDraft((prev) => ({
                      ...prev,
                      code: event.target.value.toUpperCase(),
                    }))
                  }
                  autoCapitalize="characters"
                  autoComplete="off"
                  autoCorrect="off"
                  spellCheck={false}
                  placeholder="SWAMP200"
                  disabled={editingPromoCode !== null}
                />
              </label>

              <label className="field">
                <span>{copy.admin.descriptionLabel}</span>
                <textarea
                  value={promoDraft.description}
                  onChange={(event) =>
                    setPromoDraft((prev) => ({
                      ...prev,
                      description: event.target.value,
                    }))
                  }
                  placeholder={copy.admin.descriptionPlaceholder}
                />
              </label>

              <label className="field">
                <span>{copy.admin.rewardLabel}</span>
                <input
                  type="number"
                  min="0"
                  max="5000"
                  value={promoDraft.reward_coins}
                  onChange={(event) =>
                    setPromoDraft((prev) => ({
                      ...prev,
                      reward_coins: event.target.value,
                    }))
                  }
                />
              </label>

              <div className="checkbox-row">
                <label className="checkbox-chip checkbox-chip--toggle">
                  <span>{copy.admin.unlockAllLabel}</span>
                  <input
                    type="checkbox"
                    checked={promoDraft.unlock_all_levels}
                    onChange={(event) =>
                      setPromoDraft((prev) => ({
                        ...prev,
                        unlock_all_levels: event.target.checked,
                      }))
                    }
                  />
                </label>

                <label className="checkbox-chip checkbox-chip--toggle">
                  <span>{copy.admin.promoActiveLabel}</span>
                  <input
                    type="checkbox"
                    checked={promoDraft.is_active}
                    onChange={(event) =>
                      setPromoDraft((prev) => ({
                        ...prev,
                        is_active: event.target.checked,
                      }))
                    }
                  />
                </label>
              </div>

              <button className="button button--primary" type="submit">
                {editingPromoCode ? copy.admin.savePromo : copy.admin.addPromo}
              </button>
            </form>
          </div>

          <div className="admin-list-panel">
            <div className="admin-list__header">
              <div>
                <h3>
                  {currentRoute
                    ? getRouteTitle(currentRoute, copy.common.routeNotSelected)
                    : copy.admin.questionsTitle}
                </h3>
                <p className="card-text">
                  {currentRoute
                    ? copy.admin.routeOnlyQuestions(
                        getRouteTitle(currentRoute, copy.common.routeNotSelected),
                      )
                    : copy.admin.chooseRouteLeft}
                </p>
              </div>
              {currentRoute && (
                <span className="account-chip">
                  {copy.admin.questionCount(adminQuestions.length)}
                </span>
              )}
            </div>

            <div className="admin-list">
              {adminQuestions.length === 0 ? (
                <div className="empty-state">{copy.admin.noQuestions}</div>
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
                        {copy.admin.levelTask(question.level_index + 1, question.task_index + 1)}
                      </span>
                      <strong className="admin-question-row__title">{question.prompt}</strong>
                    </button>

                    <div className="actions-row actions-row--compact">
                      <button
                        className="button button--ghost"
                        type="button"
                        onClick={() => beginEditQuestion(question)}
                      >
                        {copy.admin.edit}
                      </button>
                      <button
                        className="button button--ghost button--danger"
                        type="button"
                        onClick={() => void handleDeleteQuestion(question.id)}
                      >
                        {copy.admin.delete}
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
                      {copy.admin.levelTask(
                        selectedAdminQuestion.level_index + 1,
                        selectedAdminQuestion.task_index + 1,
                      )}
                    </span>
                    <h3>{selectedAdminQuestion.prompt}</h3>
                  </div>
                </div>

                <p>{selectedAdminQuestion.explanation}</p>

                {selectedAdminQuestion.type === "choice" && (
                  <div className="list-block">
                    <strong>{copy.admin.optionsLabel}</strong>
                    <ul>
                      {selectedAdminQuestion.options.map((option) => (
                        <li key={option}>{option}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="list-block">
                  <strong>
                    {selectedAdminQuestion.type === "choice"
                      ? copy.admin.correctAnswerChoiceLabel
                      : copy.admin.correctAnswerInputLabel}
                  </strong>
                  <ul>
                    {selectedAdminQuestion.correct_answers.map((answer) => (
                      <li key={answer}>{answer}</li>
                    ))}
                  </ul>
                </div>
              </article>
            )}

            <article className="admin-question-detail">
              <div className="admin-question-detail__header">
                <div>
                  <span className="pill">{copy.admin.promoCatalogTitle}</span>
                  <h3>{copy.admin.promoCatalogTitle}</h3>
                </div>
                <span className="account-chip">{copy.admin.promoCount(adminPromos.length)}</span>
              </div>

              {adminPromos.length === 0 ? (
                <div className="empty-state">{copy.admin.promoListEmpty}</div>
              ) : (
                <div className="admin-list">
                  {adminPromos.map((promo) => (
                    <article
                      key={promo.code}
                      className={`admin-question-row ${
                        editingPromoCode === promo.code ? "admin-question-row--selected" : ""
                      }`}
                    >
                      <button
                        type="button"
                        className="admin-question-row__select"
                        onClick={() => beginEditPromo(promo)}
                      >
                        <span className="pill" translate="no">
                          {promo.code}
                        </span>
                        <strong className="admin-question-row__title">{promo.description}</strong>
                        <span>
                          +{promo.reward_coins} {copy.account.coinsLabel} •{" "}
                          {promo.unlock_all_levels
                            ? copy.admin.promoUnlockAll
                            : copy.admin.promoNoUnlock}
                        </span>
                        <span>
                          {copy.admin.statusLabel}:{" "}
                          {promo.is_active
                            ? copy.admin.promoStatusActive
                            : copy.admin.promoStatusInactive}{" "}
                          • {copy.admin.activationsLabel}:{" "}
                          {promo.redemptions_count}
                        </span>
                      </button>

                      <div className="actions-row actions-row--compact">
                        <button
                          className="button button--ghost"
                          type="button"
                          onClick={() => beginEditPromo(promo)}
                        >
                          {copy.admin.edit}
                        </button>
                        <button
                          className="button button--ghost button--danger"
                          type="button"
                          onClick={() => void handleDeletePromo(promo.code)}
                        >
                          {copy.admin.delete}
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </article>
          </div>
        </div>
      </section>
    );
  }

  return (
    <div className="app-shell">
      <div className="bg-orb bg-orb--one" />
      <div className="bg-orb bg-orb--two" />

      <main className="panel" ref={appPanelRef}>
        <section className="hero-copy">
          <p className="eyebrow">{copy.heroEyebrow}</p>
          <h1>{copy.heroTitle}</h1>
        </section>

        {renderTopNav()}
        {renderStatusBar()}

        {view === "auth" && renderAuthView()}
        {view === "menu" && renderMenuView()}
        {view === "difficulty" && renderDifficultyView()}
        {view === "quiz" && renderQuizView()}
        {view === "daily" && renderDailyView()}
        {view === "shop" && renderShopView()}
        {view === "account" && renderAccountView()}
        {view === "leaderboard" && renderLeaderboardView()}
        {view === "admin" && renderAdminView()}
        {view === "result" && renderResultView()}

        {renderSettingsBar()}
      </main>
    </div>
  );
}

export default App;
