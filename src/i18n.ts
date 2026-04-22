export type AppLocale = "ru" | "en" | "zh";
export type ThemeMode = "dark" | "light";

export const LOCALE_STORAGE_KEY = "froggy-coder.locale";
export const THEME_STORAGE_KEY = "froggy-coder.theme";

const HTML_LANG: Record<AppLocale, string> = {
  ru: "ru-RU",
  en: "en-US",
  zh: "zh-CN",
};

const LOCALE_ORDER: AppLocale[] = ["ru", "en", "zh"];

function isAppLocale(value: string | null): value is AppLocale {
  return value === "ru" || value === "en" || value === "zh";
}

function isThemeMode(value: string | null): value is ThemeMode {
  return value === "dark" || value === "light";
}

function pluralRu(count: number, one: string, few: string, many: string) {
  const absCount = Math.abs(count);
  const lastDigit = absCount % 10;
  const lastTwoDigits = absCount % 100;

  if (lastDigit === 1 && lastTwoDigits !== 11) {
    return one;
  }

  if (lastDigit >= 2 && lastDigit <= 4 && (lastTwoDigits < 10 || lastTwoDigits >= 20)) {
    return few;
  }

  return many;
}

function countLabel(count: number, labels: { ru: [string, string, string] }) {
  return `${count} ${pluralRu(count, labels.ru[0], labels.ru[1], labels.ru[2])}`;
}

export function getHtmlLang(locale: AppLocale) {
  return HTML_LANG[locale];
}

export function getStoredLocale() {
  if (typeof window === "undefined") {
    return "ru" as const;
  }

  const storedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  if (isAppLocale(storedLocale)) {
    return storedLocale;
  }

  return "ru" as const;
}

export function getStoredTheme() {
  if (typeof window === "undefined") {
    return "dark" as const;
  }

  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (isThemeMode(storedTheme)) {
    return storedTheme;
  }

  if (window.matchMedia?.("(prefers-color-scheme: light)").matches) {
    return "light" as const;
  }

  return "dark" as const;
}

export function formatAppDate(value: string | null, locale: AppLocale) {
  if (!value) {
    return "нет данных";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString(HTML_LANG[locale], {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatAppTime(value: string | null, locale: AppLocale) {
  if (!value) {
    return "нет данных";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleTimeString(HTML_LANG[locale], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function getRouteCountLabel(locale: AppLocale, count: number) {
  void locale;
  return countLabel(count, {
    ru: ["маршрут", "маршрута", "маршрутов"],
  });
}

export function getLanguageCountLabel(locale: AppLocale, count: number) {
  void locale;
  return countLabel(count, {
    ru: ["язык", "языка", "языков"],
  });
}

export function getTaskSummaryLabel(locale: AppLocale, levelsTotal: number, tasksPerLevel: number) {
  void locale;
  return `${levelsTotal} ${pluralRu(levelsTotal, "уровень", "уровня", "уровней")} × ${tasksPerLevel} ${pluralRu(tasksPerLevel, "задача", "задачи", "задач")}`;
}

function makeLocaleNames(locale: AppLocale) {
  void locale;
  return {
    ru: "Русский",
    en: "Английский",
    zh: "Китайский",
  };
}

function makeThemeNames(locale: AppLocale) {
  void locale;
  return {
    dark: "Тёмная",
    light: "Светлая",
  };
}

function makeCommon(locale: AppLocale) {
  void locale;
return {
      genericError: "Произошла ошибка. Попробуйте еще раз.",
      routeNotSelected: "Маршрут не выбран",
      chooseLanguageAndDifficulty: "Выберите язык и сложность",
      noData: "нет данных",
      noDataShort: "Нет данных",
      answer: "Ответ",
      tag: "Тег",
      route: "Маршрут",
      skin: "Образ",
      coins: "Монеты",
      yes: "Да",
      no: "Нет",
      choiceType: "choice",
      inputType: "input",
      account: "Аккаунт",
      home: "Главная",
      levels: "Уровни",
      leaderboard: "Лидеры",
      daily: "Вопрос дня",
      shop: "Магазин",
      admin: "Админка",
      logout: "Выйти",
      back: "Назад",
      refresh: "Обновить",
      menu: "В меню",
      later: "Позже",
      save: "Сохранить",
      reset: "Сбросить",
      edit: "Редактировать",
      delete: "Удалить",
      open: "Открыть",
      close: "Скрыть",
      show: "Показать",
      hide: "Скрыть",
      or: "или",
      secondsShort: "с",
      tasksLabel: "заданий",
      login: "Вход",
      register: "Регистрация",
      continue: "Продолжить",
      start: "Начать",
      used: "Используется",
      selected: "Выбран",
      bought: "Куплен",
      notBought: "Не куплен",
      buy: "Купить",
      use: "Выбрать",
    };
}


function makeStatus(locale: AppLocale) {
  void locale;
return {
      loadingProfile: "Загружаем профиль...",
      loadingRoute: "Загружаем маршрут...",
      loadingLeaderboard: "Загружаем таблицу лидеров...",
      loadingDaily: "Загружаем ежедневный вопрос...",
      loadingAdmin: "Загружаем панель управления...",
      loadingShop: "Загружаем магазин...",
      preparingPdf: "Готовим PDF-отчет...",
      checkingPromo: "Проверяем промокод...",
      checkingDaily: "Проверяем ежедневный вопрос...",
      savingProfile: "Сохраняем профиль...",
      savingQuestion: "Сохраняем вопрос...",
      addingQuestion: "Добавляем вопрос...",
      savingPromo: "Сохраняем промокод...",
      addingPromo: "Добавляем промокод...",
      preparingLevel: "Подготавливаем уровень...",
      resettingRoute: "Сбрасываем прогресс маршрута...",
      resettingAll: "Сбрасываем общий прогресс...",
      checkingAnswer: "Проверяем ответ...",
      loggingIn: "Выполняем вход...",
      creatingAccount: "Создаем аккаунт...",
      loggingOut: "Выходим...",
      updatingCatalog: "Обновляем каталог предметов...",
      timeOut: "Время вышло. Засчитываем попытку как неверную.",
      resetConfirm: "Сбросить прогресс по всем маршрутам? Монеты, покупки и данные профиля сохранятся.",
      deletingQuestion: "Удалить вопрос?",
      deletingPromo: (code: string) => `Удалить промокод ${code}?`,
      promoCodeEmpty: "Введите промокод.",
      dailyAnswerEmpty: "Выберите или введите ответ для ежедневного вопроса.",
      profilePasswordMismatch: "Новый пароль и подтверждение должны совпадать.",
      profilePasswordMissing: "Чтобы сменить пароль, укажите новый пароль.",
      resetAllSuccess: "Прогресс по всем маршрутам сброшен.",
      genericApiFailure: "Произошла ошибка. Попробуйте еще раз.",
    };
}


function makeAuth(locale: AppLocale) {
  void locale;
return {
      eyebrow: "Аккаунт Froggy Coder",
      intro:
        "Вход в приложение с маршрутами по программированию, прогрессом по уровням и наградами за правильные ответы.",
      benefitRoutesTitle: "Маршруты и уровни",
      benefitRoutesText:
        "Выбирайте язык, сложность и проходите уровни по Python и JavaScript в удобном темпе.",
      benefitProgressTitle: "Прогресс сохраняется",
      benefitProgressText:
        "Аккаунт хранит открытые уровни, статистику маршрутов, монеты и выбранные аксессуары.",
      benefitRewardsTitle: "Награды и рейтинг",
      benefitRewardsText:
        "Получайте монеты за правильные ответы, открывайте предметы в магазине и поднимайтесь в таблице лидеров.",
      registerTitle: "Создать аккаунт",
      loginTitle: "Войти в аккаунт",
      registerKicker: "Новый аккаунт",
      welcomeBack: "С возвращением",
      registerText:
        "Создайте профиль, чтобы сохранять прогресс, монеты и купленные аксессуары. Уникальный тег будет назначен автоматически.",
      loginText:
        "Войдите, чтобы продолжить с сохраненного места. Можно использовать имя пользователя или логин в формате имя#тег.",
      registerTab: "Регистрация",
      loginTab: "Вход",
      usernameLabelLogin: "Имя пользователя или имя#тег",
      usernameLabelRegister: "Имя пользователя",
      usernamePlaceholderLogin: "frog_coder#1234",
      usernamePlaceholderRegister: "frog_coder",
      passwordLabel: "Пароль",
      passwordPlaceholder: "Минимум 6 символов",
      submitLogin: "Войти",
      submitRegister: "Создать аккаунт",
      footnoteLanguages: "Языки: Python и JavaScript",
      footnoteDifficulty: "Уровни сложности: Easy / Medium / Hard",
      successLogin: "Вход выполнен. Можно продолжать обучение.",
      successRegister: (login: string) => `Аккаунт создан. Для входа используйте логин ${login}.`,
    };
}


function makeMenu(locale: AppLocale) {
  void locale;
return {
      badge: "Главное меню",
      title: "Выберите язык и откройте нужный маршрут",
      intro:
        "Каждый маршрут разбит по сложности и уровням. Прогресс, монеты и результаты сохраняются автоматически в профиле.",
      languagesLabel: "Языков",
      routesLabel: "Маршрутов",
      walletLabel: "Монет в кошельке",
      bubble:
        "Выберите язык программирования, затем откройте нужную сложность и продолжайте с последнего доступного уровня.",
      previewTitle: "Что доступно",
      previewText:
        "Маршруты, уровни, подсказки, жизни, магазин и таблица лидеров уже доступны в приложении.",
      currentRoutePrefix: "Текущий маршрут:",
      routeCount: (count: number) => getRouteCountLabel(locale, count),
      account: "Аккаунт",
      daily: "Вопрос дня",
      shop: "Открыть магазин",
      leaderboard: "Таблица лидеров",
      resetAll: "Сбросить весь прогресс",
      currentRuns: (count: number) => `Прохождений текущего маршрута: ${count}`,
      routeHint: "Выберите язык и сложность, чтобы продолжить.",
    };
}


function makeDifficulty(locale: AppLocale) {
  void locale;
return {
      badge: "Сложность",
      title: (language: string) => `${language}: выберите уровень сложности`,
      intro:
        "Для каждой сложности доступен отдельный маршрут с собственным прогрессом, статистикой и набором уровней.",
      routeSummary: (levelsTotal: number, tasksPerLevel: number) =>
        getTaskSummaryLabel(locale, levelsTotal, tasksPerLevel),
      openRoute: "Открыть маршрут",
      refreshRoute: "Обновить маршрут",
      openedLevel: (level: number) => `Открыт уровень ${level}`,
      notStarted: "Еще не запускался",
      levelsBadge: "Уровни маршрута",
      routeLevelsTitle: "Уровни маршрута",
      currentLevel: (level: number, task: number, tasksPerLevel: number) =>
        `Сейчас активны уровень ${level} и задание ${task} из ${tasksPerLevel}.`,
      unlockedLevel: (level: number) => `Открыт уровень: ${level}`,
      completedRuns: "Завершенных забегов",
      bestScore: "Лучший счет",
      coins: "Монеты",
      availableLevels: "Доступные уровни",
      backToLanguages: "К языкам",
      resetRouteProgress: "Сбросить прогресс маршрута",
      noTasksTitle: "Уровни маршрута",
      noTasksText: "Для этого маршрута пока нет заданий. Контент для маршрута еще не добавлен.",
      openAdmin: "Открыть админку",
      continueLevel: "Продолжить",
      replayLevel: "Пройти заново",
      startLevel: "Начать",
      unavailable: "Недоступен",
      available: "Доступен",
      repeatAvailable: "Доступен повтор",
      currentTask: (task: number, total: number) => `Задание ${task} / ${total}`,
    };
}


function makeQuiz(locale: AppLocale) {
  void locale;
return {
      routeTask: "Задание маршрута",
      progressAria: "Прогресс внутри уровня",
      heartsAria: "Сердца",
      showHint: "Показать подсказку",
      hideHint: "Скрыть подсказку",
      enableTimer: (seconds: number) => `Включить таймер (${seconds}с)`,
      disableTimer: "Отключить таймер",
      timedMode: "Режим на время",
      timerAutoSubmit: "Если таймер дойдет до нуля, попытка отправится автоматически как неверная.",
      answer: "Ответ",
      checkAnswer: "Проверить ответ",
      toResults: "К результатам",
      nextTask: "Следующее задание",
      restartLevel: "Начать уровень заново",
      retry: "Повторить попытку",
      backToLevels: "К уровням",
      hintUnavailable: "Подсказка для этого задания пока не добавлена.",
      correctAnswerPrefix: "Правильный ответ:",
      answerCorrect: (coins: number) => `Правильно. +${coins} монет.`,
      answerWrong: (hearts: number) => `Неверно. Осталось жизней: ${hearts}.`,
      levelReset: "Попытки закончились. Уровень начнется заново.",
      levelResetTimeOut: "Время вышло. Попытки закончились, уровень начнется заново.",
      timeOutWrong: "Время вышло. Засчитываем попытку как неверную.",
      timeOutHearts: (hearts: number) => `Время вышло. Осталось жизней: ${hearts}.`,
      timerOff: "Таймер выключен",
      progressOpened: (currentScore: number) => `Пройдено задач: ${currentScore}`,
      task: (taskIndex: number, total: number) => `Задание ${taskIndex} / ${total}`,
      level: (levelIndex: number) => `Уровень ${levelIndex}`,
      onTime: "Таймер: ",
    };
}


function makeResult(locale: AppLocale) {
  void locale;
return {
      badge: "Результаты",
      title: (routeTitle: string) => `Маршрут завершен: ${routeTitle}`,
      scoreLine: (finalScore: number, totalQuestions: number) =>
        `Пройдено ${finalScore} из ${totalQuestions} заданий.`,
      bestScore: (score: number) => `Лучший результат на этом маршруте: ${score}.`,
      completedRuns: (count: number) => `Всего завершенных прохождений: ${count}.`,
      playAgain: "Играть снова",
      toLevels: "К уровням",
      leaders: "Лидеры",
      bubble:
        "Финиш! Результат сохранен в профиле, а лучший рекорд учтен в таблице лидеров.",
      previewTitle: "Что сохраняется после финиша",
      previewText:
        "Прогресс по маршрутам, завершенные прохождения, монеты и купленные предметы сохраняются в аккаунте автоматически.",
      caption:
        "Можно пройти маршрут еще раз, улучшить рекорд или выбрать новый маршрут.",
    };
}


function makeAccount(locale: AppLocale) {
  void locale;
return {
      badge: "Профиль",
      subtitle:
        "Здесь можно обновить имя пользователя и пароль. Уникальный тег сохраняется и остается частью логина.",
      tagHint:
        "Тег закреплен за профилем. При смене имени обновится и полный логин формата имя#тег.",
      routeLabel: "Маршрут",
      skinLabel: "Образ",
      coinsLabel: "Монеты",
      settingsTitle: "Настройки профиля",
      loginBadge: (login: string) => `Логин: ${login}`,
      usernameLabel: "Имя пользователя",
      tagLabel: "Тег",
      loginLabel: "Логин для следующих входов",
      currentPassword: "Текущий пароль",
      currentPasswordPlaceholder: "Требуется только при смене пароля",
      newPassword: "Новый пароль",
      repeatNewPassword: "Повторите новый пароль",
      passwordHint: "Если пароль менять не нужно, оставьте поля пустыми.",
      saveChanges: "Сохранить изменения",
      resetChanges: "Сбросить изменения",
      loginAfterChangeTitle: "Вход после смены имени",
      loginAfterChangeText: (login: string) =>
        `После сохранения используйте новый логин ${login}. Текущая сессия при этом не прервется.`,
      progressBadgeSelected: "Выбран маршрут",
      progressBadgeEmpty: "Маршрут не выбран",
      progressTitle: "Статистика маршрута",
      routeForProgress: "Маршрут для прогресса",
      openedTasks: (opened: number, total: number | null) =>
        total ? `из ${total} заданий открыто` : `${opened} открытых заданий`,
      progressEmpty: "прогресс по этому маршруту пока не зафиксирован",
      bestScore: "Лучший счет",
      runs: "Забеги",
      unlockedLevel: "Открыт уровень",
      openRoute: "Открыть маршрут",
      downloadPdf: "Скачать PDF-отчет",
      pdfReady: "PDF-отчет сформирован.",
      shop: "Магазин",
      promoBadge: "ПРОМОКОД",
      promoTitle: "Бонус для аккаунта",
      promoCode: "Промокод",
      promoHint:
        "Можно активировать системные и админские промокоды. Например, FROGBEST открывает все уровни и добавляет 1000 монет, а новые коды администратор может выпускать прямо из панели управления.",
      activatePromo: "Активировать промокод",
      profileSaved: "Профиль обновлен.",
      promoActivated: "Промокод активирован.",
    };
}


function makeDaily(locale: AppLocale) {
  void locale;
return {
      badge: "Вопрос дня",
      titlePrefix: "Ежедневный челлендж на",
      subtitle: (rewardCoins: number) =>
        `Один общий вопрос для всех игроков. За правильный ответ начисляется +${rewardCoins} монет.`,
      dateLabel: "Дата",
      statusLabel: "Статус",
      answeredLabel: "уже отвечен",
      pendingLabel: "ожидает ответ",
      questionLabel: "Общий вопрос для всех игроков",
      answerButton: "Ответить",
      laterButton: "Позже",
      menuButton: "В меню",
      accountButton: "В аккаунт",
      leaderboardTitle: "Лидерборд дня",
      leaderboardEmpty: "Пока нет правильных ответов. Можно открыть сегодняшний рейтинг первым.",
      howItWorksTitle: "Как это работает",
      howItWorksText:
        "В лидерборд попадают только правильные ответы, а места зависят от времени отправки. Повторно ответить в этот же день нельзя.",
      answerCorrect: (rewardCoins: number) => `Правильно. +${rewardCoins} монет.`,
      answerSavedWrong: "Ответ сохранен, но он оказался неверным.",
      correctAnswerPrefix: "Правильный ответ:",
      explanationPrefix: "Объяснение:",
      answeredAtPrefix: "Отмечено:",
      submitHint: "Выберите или введите ответ для ежедневного вопроса.",
      bubble: "Общий вопрос обновляется раз в день. После правильного ответа можно сразу посмотреть, кто решил быстрее всех.",
    };
}


function makeLeaderboard(locale: AppLocale) {
  void locale;
return {
      badge: "Таблица лидеров",
      titlePrefix: "Таблица лидеров:",
      globalScope: "Статистика по всем игрокам.",
      routeScope: (routeLabel: string) => `Статистика для маршрута ${routeLabel}.`,
      allRoutes: "Все маршруты",
      coins: "Монеты",
      emptyState: "По этой метрике пока нет данных.",
      back: "Назад",
      refresh: "Обновить",
      lastPlayed: "Последний финиш:",
    };
}


function makeShop(locale: AppLocale) {
  void locale;
return {
      badge: "Магазин",
      title: "Аксессуары и предметы профиля",
      intro:
        "Покупайте предметы за монеты, которые начисляются за правильные ответы в заданиях.",
      coinsLabel: "Монеты",
      ownedLabel: "Открыто предметов",
      skinLabel: "Активный образ",
      howEarnTitle: "Как зарабатываются монеты",
      howEarnText:
        "За каждый правильный ответ начисляется +10 монет. Ошибки не списывают уже накопленный баланс.",
      catalogUpdated: "Данные магазина обновлены.",
      activeItem: "Используется",
      buyFor: (price: number) => `Купить за ${price}`,
      buy: "Купить",
      select: "Выбрать",
      bought: "Куплен",
      notBought: "Не куплен",
      baseItem: "Базовый предмет",
      menu: "В меню",
      levels: "К уровням",
    };
}


function makeAdmin(locale: AppLocale) {
  void locale;
return {
      badge: "Управление контентом",
      title: "Вопросы и маршруты",
      intro:
        "Добавляйте и редактируйте задания для конкретных языков, сложностей и уровней.",
      newQuestionTitle: "Новый вопрос",
      editQuestionTitle: "Редактирование вопроса",
      resetForm: "Сбросить форму",
      routeLabel: "Маршрут",
      questionType: "Тип вопроса",
      orderIndex: "Порядок в маршруте",
      questionText: "Текст вопроса",
      hintExplanation: "Подсказка / объяснение",
      placeholder: "Плейсхолдер для текстового ответа",
      optionsLabel: "Варианты ответа, по одному в строке",
      correctAnswerChoiceLabel: "Правильный ответ",
      correctAnswerInputLabel: "Допустимые ответы, по одному в строке",
      saveQuestion: "Сохранить вопрос",
      addQuestion: "Добавить вопрос",
      newPromoTitle: "Новый промокод",
      editPromoTitle: "Редактирование промокода",
      codeLabel: "Код промокода",
      descriptionLabel: "Описание",
      descriptionPlaceholder: "Что делает этот промокод",
      rewardLabel: "Награда в монетах",
      unlockAllLabel: "Открыть все уровни",
      promoActiveLabel: "Промокод активен",
      savePromo: "Сохранить промокод",
      addPromo: "Добавить промокод",
      questionsTitle: "Список вопросов",
      routeOnlyQuestions: (routeTitle: string) => `Показаны только вопросы маршрута ${routeTitle}.`,
      chooseRouteLeft: "Выбери маршрут слева, чтобы увидеть его вопросы.",
      questionCount: (count: number) => `Вопросов: ${count}`,
      noQuestions: "Для этого маршрута пока нет вопросов.",
      promoCatalogTitle: "Каталог бонусов",
      promoCount: (count: number) => `Всего кодов: ${count}`,
      statusLabel: "Статус",
      activationsLabel: "Активаций",
      edit: "Редактировать",
      delete: "Удалить",
      levelTask: (level: number, task: number) => `Уровень ${level} • Задание ${task}`,
      promoUnlockAll: "открывает все уровни",
      promoNoUnlock: "без разблокировки уровней",
      promoStatusActive: "активен",
      promoStatusInactive: "выключен",
      promoListEmpty: "Промокодов пока нет.",
      defaultOptionsText: "Вариант 1\nВариант 2",
      defaultAnswersText: "Вариант 1",
      questionOpened: "Вопрос открыт для редактирования.",
      promoOpened: "Промокод открыт для редактирования.",
      questionSaved: "Вопрос обновлен.",
      questionAdded: "Вопрос добавлен.",
      promoSaved: "Промокод обновлен.",
      promoAdded: "Промокод добавлен.",
      questionDeleted: "Вопрос удален.",
      promoDeleted: "Промокод удален.",
    };
}


export type AppCopy = ReturnType<typeof createAppCopy>;

export function createAppCopy(locale: AppLocale) {
  const sourceLocale: AppLocale = "ru";

  return {
    appTitle: "Froggy Coder",
    appSubtitle: "Практика по программированию",
    heroTitle: "Маршруты, уровни и прогресс в одном приложении",
    heroEyebrow: "Froggy Coder • Практика по программированию",
    settings: {
      title: "Настройки интерфейса",
      themeLabel: "Тема",
      languageLabel: "Язык",
      localeNames: makeLocaleNames(sourceLocale),
      themeNames: makeThemeNames(sourceLocale),
    },
    common: makeCommon(sourceLocale),
    status: makeStatus(sourceLocale),
    auth: makeAuth(sourceLocale),
    menu: makeMenu(sourceLocale),
    difficulty: makeDifficulty(sourceLocale),
    quiz: makeQuiz(sourceLocale),
    result: makeResult(sourceLocale),
    account: makeAccount(sourceLocale),
    daily: makeDaily(sourceLocale),
    leaderboard: makeLeaderboard(sourceLocale),
    shop: makeShop(sourceLocale),
    admin: makeAdmin(sourceLocale),
    formatRouteCount: (count: number) => getRouteCountLabel(sourceLocale, count),
    formatLanguageCount: (count: number) => getLanguageCountLabel(sourceLocale, count),
    formatTaskSummary: (levelsTotal: number, tasksPerLevel: number) =>
      getTaskSummaryLabel(sourceLocale, levelsTotal, tasksPerLevel),
    locale,
    localeOrder: LOCALE_ORDER,
  };
}
