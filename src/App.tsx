import { useEffect, useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import bolotoBackdrop from "../boloto.png";
import swampBackdrop from "../swamp_bg.png";
import winBackdrop from "../win.jpg";
import {
  ApiError,
  clearStoredToken,
  createAdminQuestion,
  deleteAdminQuestion,
  getAdminQuestions,
  getBootstrap,
  getLeaderboard,
  loadStoredToken,
  login,
  logout,
  persistToken,
  register,
  resetProgress,
  submitAnswer,
  updateAdminQuestion,
} from "./api";
import type {
  AdminQuestion,
  AdminQuestionPayload,
  AnswerResult,
  AuthResponse,
  Credentials,
  LeaderboardEntry,
  Progress,
  Question,
  QuestionDraft,
  User,
} from "./types";

type View = "auth" | "dashboard" | "quiz" | "leaderboard" | "admin" | "result";
type AuthMode = "login" | "register";

type RoundResult = {
  finalScore: number;
  totalQuestions: number;
  bestScore: number;
};

const TOPIC = "python";
const APP_TITLE = "Froggy Coder";
const AUTH_SCENE_STYLE: CSSProperties = {
  backgroundImage: `linear-gradient(180deg, rgba(8, 18, 14, 0.18), rgba(8, 18, 14, 0.72)), url(${bolotoBackdrop})`,
};
const DASHBOARD_SCENE_STYLE: CSSProperties = {
  backgroundImage: `linear-gradient(180deg, rgba(8, 18, 14, 0.1), rgba(8, 18, 14, 0.72)), url(${swampBackdrop})`,
};
const RESULT_SCENE_STYLE: CSSProperties = {
  backgroundImage: `linear-gradient(180deg, rgba(8, 18, 14, 0.1), rgba(8, 18, 14, 0.68)), url(${winBackdrop})`,
};

function createEmptyDraft(): QuestionDraft {
  return {
    topic: TOPIC,
    type: "choice",
    prompt: "",
    explanation: "",
    placeholder: "",
    order_index: "0",
    options_text: "Ответ 1\nОтвет 2",
    answers_text: "Ответ 1",
  };
}

function normalizeWhitespace(value: string) {
  return value.trim().replace(/\s+/g, " ");
}

function formatDate(value: string | null) {
  if (!value) {
    return "еще нет";
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

function App() {
  const [view, setView] = useState<View>("auth");
  const [authMode, setAuthMode] = useState<AuthMode>("register");
  const [token, setToken] = useState<string | null>(() => loadStoredToken());

  const [user, setUser] = useState<User | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [adminQuestions, setAdminQuestions] = useState<AdminQuestion[]>([]);

  const [authForm, setAuthForm] = useState<Credentials>({
    username: "",
    password: "",
  });

  const [selectedOption, setSelectedOption] = useState("");
  const [typedAnswer, setTypedAnswer] = useState("");
  const [feedback, setFeedback] = useState<AnswerResult | null>(null);
  const [pendingProgress, setPendingProgress] = useState<Progress | null>(null);
  const [displayIndex, setDisplayIndex] = useState(0);
  const [roundResult, setRoundResult] = useState<RoundResult | null>(null);

  const [draft, setDraft] = useState<QuestionDraft>(() => createEmptyDraft());
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);

  const [busyLabel, setBusyLabel] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const currentQuestion = questions[displayIndex] ?? null;
  const currentAnswer =
    currentQuestion?.type === "choice" ? selectedOption : typedAnswer;
  const canSubmitAnswer =
    currentQuestion !== null &&
    currentAnswer.trim().length > 0 &&
    feedback === null &&
    busyLabel.length === 0;

  const displayedScore =
    progress === null
      ? 0
      : progress.current_score + (feedback?.is_correct ? 1 : 0);

  useEffect(() => {
    if (token) {
      void hydrateSession(token, "dashboard");
    }
  }, []);

  async function hydrateSession(activeToken: string, nextView: View = "dashboard") {
    setBusyLabel("Поднимаем серверное болото...");
    setErrorMessage("");

    try {
      const bootstrap = await getBootstrap(activeToken, TOPIC);
      const leaderboardResponse = await getLeaderboard(TOPIC);

      setUser(bootstrap.user);
      setQuestions(bootstrap.questions);
      setProgress(bootstrap.progress);
      setLeaderboard(leaderboardResponse.entries);
      setDisplayIndex(bootstrap.progress.current_index);

      if (bootstrap.user.is_admin) {
        const adminData = await getAdminQuestions(activeToken, TOPIC);
        setAdminQuestions(adminData);
      } else {
        setAdminQuestions([]);
      }

      setView(nextView);
    } catch (error) {
      handleApiFailure(error, true);
    } finally {
      setBusyLabel("");
    }
  }

  function resetQuestionUi() {
    setSelectedOption("");
    setTypedAnswer("");
    setFeedback(null);
    setPendingProgress(null);
  }

  function resetDraftForm() {
    setDraft(createEmptyDraft());
    setEditingQuestionId(null);
  }

  function storeSession(authResponse: AuthResponse) {
    persistToken(authResponse.token);
    setToken(authResponse.token);
    setUser(authResponse.user);
  }

  function clearSession() {
    clearStoredToken();
    setToken(null);
    setUser(null);
    setQuestions([]);
    setProgress(null);
    setLeaderboard([]);
    setAdminQuestions([]);
    setRoundResult(null);
    resetQuestionUi();
    resetDraftForm();
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

    setErrorMessage("Произошла непредвиденная ошибка.");
  }

  async function handleAuthSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyLabel(authMode === "login" ? "Входим в болото..." : "Создаем аккаунт...");
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
          ? "С возвращением в Froggy Coder."
          : "Аккаунт создан. Теперь прогресс будет храниться на сервере.",
      );
      await hydrateSession(response.token, "dashboard");
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function handleLogout() {
    if (!token) {
      clearSession();
      return;
    }

    setBusyLabel("Выходим...");
    setErrorMessage("");

    try {
      await logout(token);
    } catch {
      // Ignore logout transport errors and still clear the local session.
    } finally {
      clearSession();
      setBusyLabel("");
    }
  }

  async function refreshLeaderboard() {
    try {
      const response = await getLeaderboard(TOPIC);
      setLeaderboard(response.entries);
    } catch (error) {
      handleApiFailure(error);
    }
  }

  async function openLeaderboard() {
    setBusyLabel("Обновляем таблицу лидеров...");
    setErrorMessage("");

    try {
      await refreshLeaderboard();
      setView("leaderboard");
    } finally {
      setBusyLabel("");
    }
  }

  async function openAdmin() {
    if (!token || !user?.is_admin) {
      return;
    }

    setBusyLabel("Открываем админку...");
    setErrorMessage("");

    try {
      const data = await getAdminQuestions(token, TOPIC);
      setAdminQuestions(data);
      setView("admin");
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function startRun(resetServerProgress = false) {
    if (!token || !progress) {
      return;
    }

    setBusyLabel(resetServerProgress ? "Готовим новый забег..." : "Прыгаем на маршрут...");
    setErrorMessage("");
    setSuccessMessage("");

    try {
      let nextProgress = progress;

      if (resetServerProgress) {
        nextProgress = await resetProgress(token, TOPIC);
        setProgress(nextProgress);
      }

      setDisplayIndex(nextProgress.current_index);
      setRoundResult(null);
      resetQuestionUi();
      setView("quiz");
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function handleSubmitAnswer() {
    if (!token || !currentQuestion || !canSubmitAnswer) {
      return;
    }

    setBusyLabel("Проверяем прыжок...");
    setErrorMessage("");

    try {
      const result = await submitAnswer(token, {
        topic: TOPIC,
        question_id: currentQuestion.id,
        answer: currentAnswer,
      });

      setFeedback(result);
      setPendingProgress(result.next_progress);

      if (result.quiz_completed) {
        setRoundResult({
          finalScore: result.final_score ?? 0,
          totalQuestions: result.total_questions,
          bestScore: result.next_progress.best_score,
        });
        await refreshLeaderboard();
      }
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  function handleNextAfterFeedback() {
    if (!feedback || !pendingProgress) {
      return;
    }

    setProgress(pendingProgress);

    if (feedback.quiz_completed) {
      resetQuestionUi();
      setDisplayIndex(0);
      setView("result");
      return;
    }

    setDisplayIndex(pendingProgress.current_index);
    resetQuestionUi();
  }

  function beginEditQuestion(question: AdminQuestion) {
    setEditingQuestionId(question.id);
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
    setSuccessMessage("Режим редактирования включен.");
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
      topic: draft.topic.trim().toLowerCase() || TOPIC,
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
    if (!token || !user?.is_admin) {
      return;
    }

    setBusyLabel(editingQuestionId ? "Сохраняем изменения..." : "Добавляем вопрос...");
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const payload = buildPayloadFromDraft();

      if (editingQuestionId) {
        await updateAdminQuestion(token, editingQuestionId, payload);
        setSuccessMessage("Вопрос обновлен.");
      } else {
        await createAdminQuestion(token, payload);
        setSuccessMessage("Новый вопрос добавлен.");
      }

      resetDraftForm();
      await hydrateSession(token, "admin");
    } catch (error) {
      handleApiFailure(error);
    } finally {
      setBusyLabel("");
    }
  }

  async function handleDeleteQuestion(questionId: number) {
    if (!token || !user?.is_admin) {
      return;
    }

    const confirmed = window.confirm("Удалить этот вопрос из базы?");
    if (!confirmed) {
      return;
    }

    setBusyLabel("Удаляем вопрос...");
    setErrorMessage("");
    setSuccessMessage("");

    try {
      await deleteAdminQuestion(token, questionId);
      if (editingQuestionId === questionId) {
        resetDraftForm();
      }
      setSuccessMessage("Вопрос удален.");
      await hydrateSession(token, "admin");
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
          <span className="top-nav__frog" aria-hidden="true">
            🐸
          </span>
          <div>
            <strong>{user.username}</strong>
            <span>{user.is_admin ? "Админ болота" : "Игрок маршрута"}</span>
          </div>
        </div>

        <div className="top-nav__actions">
          <button className="button button--ghost" onClick={() => setView("dashboard")}>
            Главная
          </button>
          <button className="button button--ghost" onClick={openLeaderboard}>
            Лидеры
          </button>
          {user.is_admin && (
            <button className="button button--ghost" onClick={openAdmin}>
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
      <section className="card">
        <div className="scene-layout">
          <div className="scene-copy">
            <div className="card-badge">Portfolio Fullstack Edition</div>
            <h2>Теперь это уже настоящий fullstack-проект</h2>
            <p className="card-text">
              В старой версии прогресс жил локально в Python-игре. Теперь у нас
              есть backend на FastAPI, SQLite, регистрация, лидерборд и админка
              для вопросов.
            </p>

            <div className="stats-row">
              <div className="stat-box">
                <span className="stat-label">Frontend</span>
                <strong>React + Vite + TypeScript</strong>
              </div>
              <div className="stat-box">
                <span className="stat-label">Backend</span>
                <strong>FastAPI + SQLite</strong>
              </div>
              <div className="stat-box">
                <span className="stat-label">Источник правды</span>
                <strong>Сервер и база данных</strong>
              </div>
            </div>
          </div>

          <div className="scene-art" style={AUTH_SCENE_STYLE}>
            <div className="frog-bubble">
              Ква! Входи в аккаунт и болото начнет хранить твой прогресс,
              результаты и место в таблице лидеров.
            </div>

            <form className="auth-card" onSubmit={handleAuthSubmit}>
              <div className="mode-switch">
                <button
                  type="button"
                  className={`mode-switch__btn ${
                    authMode === "register" ? "mode-switch__btn--active" : ""
                  }`}
                  onClick={() => setAuthMode("register")}
                >
                  Регистрация
                </button>
                <button
                  type="button"
                  className={`mode-switch__btn ${
                    authMode === "login" ? "mode-switch__btn--active" : ""
                  }`}
                  onClick={() => setAuthMode("login")}
                >
                  Вход
                </button>
              </div>

              <label className="field">
                <span>Имя пользователя</span>
                <input
                  value={authForm.username}
                  onChange={(event) =>
                    setAuthForm((prev) => ({ ...prev, username: event.target.value }))
                  }
                  placeholder="frog_coder"
                />
              </label>

              <label className="field">
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
                {authMode === "login" ? "Войти в болото" : "Создать аккаунт"}
              </button>
            </form>
          </div>
        </div>
      </section>
    );
  }

  function renderDashboardView() {
    const hasProgress = progress !== null && progress.current_index > 0;

    return (
      <section className="card">
        <div className="scene-layout">
          <div className="scene-copy">
            <div className="card-badge">Серверный профиль игрока</div>
            <h2>{APP_TITLE} теперь хранит прогресс на backend</h2>
            <p className="card-text">
              Это уже не локальная демка. Пользователь регистрируется, играет,
              получает результат, попадает в лидерборд, а вопросы хранятся и
              редактируются через админку.
            </p>

            <div className="stats-row">
              <div className="stat-box">
                <span className="stat-label">Текущий маршрут</span>
                <strong>
                  {progress ? `${progress.current_index}/${progress.total_questions}` : "0/0"}
                </strong>
              </div>
              <div className="stat-box">
                <span className="stat-label">Лучший результат</span>
                <strong>{progress ? progress.best_score : 0}</strong>
              </div>
              <div className="stat-box">
                <span className="stat-label">Завершенные забеги</span>
                <strong>{progress ? progress.completed_runs : 0}</strong>
              </div>
            </div>

            <div className="actions-row">
              <button className="button button--primary" onClick={() => void startRun(false)}>
                {hasProgress
                  ? `Продолжить с кочки ${progress!.current_index + 1}`
                  : "Начать новый забег"}
              </button>
              <button className="button button--ghost" onClick={() => void startRun(true)}>
                Сбросить и начать сначала
              </button>
              <button className="button button--ghost" onClick={openLeaderboard}>
                Таблица лидеров
              </button>
              {user?.is_admin && (
                <button className="button button--ghost" onClick={openAdmin}>
                  Открыть админку
                </button>
              )}
            </div>
          </div>

          <div className="scene-art" style={DASHBOARD_SCENE_STYLE}>
            <div className="frog-bubble">
              Ква! Теперь каждый прыжок уходит на сервер: аккаунты, прогресс,
              лидерборд и вопросы для будущих игроков.
            </div>

            <div className="preview-panel">
              <h3>Топ болота</h3>
              {leaderboard.length === 0 ? (
                <p>Лидерборд пока пуст. Стань первым в таблице.</p>
              ) : (
                <ol className="leaderboard-mini">
                  {leaderboard.slice(0, 5).map((entry) => (
                    <li key={entry.rank}>
                      <span>#{entry.rank}</span>
                      <strong>{entry.username}</strong>
                      <em>{entry.best_score}</em>
                    </li>
                  ))}
                </ol>
              )}
            </div>

            <p className="scene-caption">
              Старый вайб с болотом остался, но архитектура уже как у
              полноценного портфолио-проекта.
            </p>
          </div>
        </div>
      </section>
    );
  }

  function renderQuizView() {
    if (!currentQuestion || !progress) {
      return null;
    }

    return (
      <section className="card card--quiz">
        <div className="quiz-topbar">
          <div>
            <p className="eyebrow">Серверный забег</p>
            <h2>
              {APP_TITLE}: Python swamp run
            </h2>
          </div>

          <div className="quiz-meta">
            <span>
              Кочка {displayIndex + 1} / {progress.total_questions}
            </span>
            <span>Текущий счет: {displayedScore}</span>
          </div>
        </div>

        <div className="lily-row" aria-label="Карта прогресса">
          {questions.map((question, index) => {
            const isAnswered = index < displayIndex;
            const isCurrent = index === displayIndex;

            return (
              <div
                key={question.id}
                className={`lily-pad ${
                  isAnswered
                    ? "lily-pad--done"
                    : isCurrent
                      ? "lily-pad--current"
                      : "lily-pad--next"
                }`}
              >
                <span>{index + 1}</span>
              </div>
            );
          })}
        </div>

        <div className="frog-hint">
          <span className="frog-hint__emoji" aria-hidden="true">
            🐸
          </span>
          <span>
            {feedback
              ? feedback.is_correct
                ? "Хороший прыжок. Сервер уже сохранил его в прогресс."
                : "Нормально. Ошибка тоже записана, а объяснение поможет дойти дальше."
              : "Ответ проверяет backend, а фронт только показывает маршрут и реакцию лягушки."}
          </span>
        </div>

        <div className="question-box">
          <p className="question-number">Вопрос из базы данных</p>
          <h3>{currentQuestion.prompt}</h3>
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
            <span>Код для прыжка</span>
            <input
              value={typedAnswer}
              placeholder={currentQuestion.placeholder ?? "Введи ответ"}
              onChange={(event) => setTypedAnswer(event.target.value)}
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
                ? "Ква, верно. Прыжок засчитан."
                : "Прыжок мимо кочки."}
            </strong>
            {!feedback.is_correct && (
              <span>
                Правильный ответ: {feedback.correct_answers.join(" или ")}
              </span>
            )}
            <span>{feedback.explanation}</span>
          </div>
        )}

        <div className="actions-row">
          <button
            className="button button--primary"
            onClick={feedback ? handleNextAfterFeedback : () => void handleSubmitAnswer()}
            disabled={!feedback && !canSubmitAnswer}
          >
            {feedback
              ? feedback.quiz_completed
                ? "К экрану результата"
                : "На следующую кочку"
              : "Проверить на сервере"}
          </button>

          <button className="button button--ghost" onClick={() => setView("dashboard")}>
            На главную
          </button>
        </div>
      </section>
    );
  }

  function renderResultView() {
    if (!roundResult || !progress) {
      return null;
    }

    return (
      <section className="card">
        <div className="scene-layout">
          <div className="scene-copy">
            <div className="card-badge">Финиш и запись в лидерборд</div>
            <h2>Забег завершен и сохранен на сервере</h2>
            <p className="score-line">
              Итог: <strong>{roundResult.finalScore}</strong> из{" "}
              <strong>{roundResult.totalQuestions}</strong>
            </p>
            <p className="card-text">
              Лучший результат в профиле: <strong>{roundResult.bestScore}</strong>.
              Завершенных забегов: <strong>{progress.completed_runs}</strong>.
            </p>

            <div className="result-ring">
              <span>
                {Math.round(
                  (roundResult.finalScore / roundResult.totalQuestions) * 100,
                )}
                %
              </span>
            </div>

            <div className="actions-row">
              <button className="button button--primary" onClick={() => void startRun(true)}>
                Новый забег
              </button>
              <button className="button button--ghost" onClick={openLeaderboard}>
                Посмотреть лидеров
              </button>
              <button className="button button--ghost" onClick={() => setView("dashboard")}>
                Вернуться в профиль
              </button>
            </div>
          </div>

          <div className="scene-art" style={RESULT_SCENE_STYLE}>
            <div className="frog-bubble frog-bubble--result">
              Ква! Теперь результат не исчезает после перезапуска. Он уже в базе
              и может попасть в таблицу лидеров.
            </div>

            <div className="preview-panel">
              <h3>Смысл fullstack-версии</h3>
              <p>
                Frontend рисует маршрут, backend проверяет ответы, база хранит
                аккаунты, прогресс и лучшие забеги.
              </p>
            </div>

            <p className="scene-caption">
              Это уже выглядит как проект, который можно показывать в портфолио.
            </p>
          </div>
        </div>
      </section>
    );
  }

  function renderLeaderboardView() {
    return (
      <section className="card">
        <div className="card-badge">Таблица лидеров</div>
        <h2>Лучшие прыгуны по Python-болоту</h2>
        <p className="card-text">
          Лидерборд строится из серверных результатов, а не из локального
          состояния браузера.
        </p>

        {leaderboard.length === 0 ? (
          <div className="empty-state">
            Пока никто не завершил маршрут. Первый финиш будет твоим.
          </div>
        ) : (
          <div className="leaderboard-list">
            {leaderboard.map((entry) => (
              <div key={`${entry.rank}-${entry.username}`} className="leaderboard-row">
                <div className="leaderboard-row__rank">#{entry.rank}</div>
                <div className="leaderboard-row__meta">
                  <strong>{entry.username}</strong>
                  <span>Последний финиш: {formatDate(entry.last_played_at)}</span>
                </div>
                <div className="leaderboard-row__score">
                  <span>Лучший счет: {entry.best_score}</span>
                  <span>Забегов: {entry.completed_runs}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="actions-row">
          <button className="button button--primary" onClick={() => setView("dashboard")}>
            Назад
          </button>
          <button className="button button--ghost" onClick={() => void refreshLeaderboard()}>
            Обновить
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
        <div className="card-badge">Админка контента</div>
        <h2>Вопросы теперь живут в базе данных</h2>
        <p className="card-text">
          Здесь можно добавлять, редактировать и удалять вопросы без правки
          фронтенд-кода. Это уже нормальный CMS-lite для учебного проекта.
        </p>

        <div className="admin-grid">
          <form className="admin-form" onSubmit={handleSaveQuestion}>
            <div className="admin-form__header">
              <h3>{editingQuestionId ? "Редактирование вопроса" : "Новый вопрос"}</h3>
              {editingQuestionId && (
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={resetDraftForm}
                >
                  Сбросить форму
                </button>
              )}
            </div>

            <label className="field">
              <span>Тема</span>
              <input
                value={draft.topic}
                onChange={(event) =>
                  setDraft((prev) => ({ ...prev, topic: event.target.value }))
                }
              />
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
              <span>Порядок на маршруте</span>
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
              <span>Объяснение после ответа</span>
              <textarea
                value={draft.explanation}
                onChange={(event) =>
                  setDraft((prev) => ({ ...prev, explanation: event.target.value }))
                }
              />
            </label>

            <label className="field">
              <span>Placeholder для input-вопроса</span>
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
                  : "Правильные ответы, по одному в строке"}
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

          <div className="admin-list">
            {adminQuestions.length === 0 ? (
              <div className="empty-state">В базе пока нет вопросов.</div>
            ) : (
              adminQuestions.map((question) => (
                <article key={question.id} className="admin-question-card">
                  <div className="admin-question-card__header">
                    <div>
                      <span className="pill">
                        #{question.order_index} • {question.type}
                      </span>
                      <h3>{question.prompt}</h3>
                    </div>

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
                  </div>

                  <p>{question.explanation}</p>

                  {question.type === "choice" && (
                    <div className="list-block">
                      <strong>Варианты:</strong>
                      <ul>
                        {question.options.map((option) => (
                          <li key={option}>{option}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="list-block">
                    <strong>Правильные ответы:</strong>
                    <ul>
                      {question.correct_answers.map((answer) => (
                        <li key={answer}>{answer}</li>
                      ))}
                    </ul>
                  </div>
                </article>
              ))
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
          <p className="eyebrow">{APP_TITLE} • Fullstack Swamp Portfolio</p>
          <h1>Лягушка выросла из локальной игры в полноценный fullstack</h1>
          <p className="hero-text">
            Теперь это не просто фронтенд-квиз. У проекта есть backend API,
            база данных, серверный прогресс, лидерборд, админка и понятная
            архитектура для портфолио junior Python/fullstack разработчика.
          </p>
        </section>

        {renderTopNav()}
        {renderStatusBar()}

        {view === "auth" && renderAuthView()}
        {view === "dashboard" && renderDashboardView()}
        {view === "quiz" && renderQuizView()}
        {view === "leaderboard" && renderLeaderboardView()}
        {view === "admin" && renderAdminView()}
        {view === "result" && renderResultView()}
      </main>
    </div>
  );
}

export default App;
