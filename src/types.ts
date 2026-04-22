export type User = {
  id: number;
  username: string;
  tag: string | null;
  full_username: string;
  is_admin: boolean;
  coins: number;
  inventory: string[];
  active_skin: string;
  active_skin_label: string;
  active_skin_icon: string;
};

export type RouteOption = {
  topic: string;
  language: string;
  difficulty: string;
  difficulty_label: string;
  levels_total: number;
  questions_total: number;
  tasks_per_level: number;
};

export type RouteListResponse = {
  items: RouteOption[];
};

export type Question = {
  id: number;
  topic: string;
  language: string;
  difficulty: string;
  level_index: number;
  task_index: number;
  type: "choice" | "input";
  prompt: string;
  options: string[];
  placeholder: string | null;
  hint: string;
  order_index: number;
};

export type Progress = {
  topic: string;
  current_index: number;
  current_score: number;
  opened_questions: number;
  best_score: number;
  completed_runs: number;
  remaining_hearts: number;
  total_questions: number;
  levels_total: number;
  tasks_per_level: number;
  current_level_index: number;
  current_task_index: number;
  unlocked_level_index: number;
  next_question_id: number | null;
};

export type BootstrapResponse = {
  user: User;
  questions: Question[];
  progress: Progress;
};

export type ProgressListResponse = {
  items: Progress[];
};

export type Credentials = {
  username: string;
  password: string;
};

export type AuthResponse = {
  user: User;
  csrf_token: string;
};

export type SessionResponse = AuthResponse;

export type AccountUpdatePayload = {
  display_name: string;
  current_password?: string;
  new_password?: string;
};

export type PromoRedeemPayload = {
  code: string;
};

export type PromoRedeemResponse = {
  user: User;
  progresses: Progress[];
  message: string;
};

export type PromoCode = {
  code: string;
  description: string;
  reward_coins: number;
  unlock_all_levels: boolean;
  is_active: boolean;
  redemptions_count: number;
};

export type PromoCodePayload = {
  code: string;
  description: string;
  reward_coins: number;
  unlock_all_levels: boolean;
  is_active: boolean;
};

export type PromoCodeListResponse = {
  items: PromoCode[];
};

export type TranslationBatchResponse = {
  texts: string[];
};

export type SubmitAnswerPayload = {
  topic: string;
  question_id: number;
  answer: string;
};

export type SelectLevelPayload = {
  topic: string;
  level_index: number;
};

export type TopicPayload = {
  topic: string;
};

export type DailyChallengeEntry = {
  rank: number;
  username: string;
  tag: string | null;
  full_username: string;
  is_correct: boolean;
  answered_at: string | null;
};

export type DailyChallengeResult = {
  is_correct: boolean;
  correct_answers: string[];
  explanation: string;
  reward_coins: number;
  answered_at: string;
};

export type DailyChallengeResponse = {
  challenge_date: string;
  question: Question;
  reward_coins: number;
  already_answered: boolean;
  result: DailyChallengeResult | null;
  leaderboard: DailyChallengeEntry[];
};

export type DailyChallengeSubmitPayload = {
  answer: string;
};

export type DailyChallengeSubmitResponse = DailyChallengeResult & {
  challenge_date: string;
  user: User;
  leaderboard: DailyChallengeEntry[];
};

export type AnswerResult = {
  is_correct: boolean;
  correct_answers: string[];
  explanation: string;
  next_progress: Progress;
  user: User;
  coins_awarded: number;
  quiz_completed: boolean;
  final_score: number | null;
  total_questions: number;
};

export type LeaderboardMetric = "best_score" | "completed_runs" | "coins";

export type LeaderboardEntry = {
  rank: number;
  username: string;
  tag: string | null;
  full_username: string;
  metric_value: number;
  best_score: number;
  completed_runs: number;
  coins: number;
  last_played_at: string | null;
};

export type LeaderboardResponse = {
  topic: string;
  metric: LeaderboardMetric;
  metric_label: string;
  scope: "route" | "global";
  entries: LeaderboardEntry[];
};

export type ShopItem = {
  id: string;
  name: string;
  description: string;
  price: number;
  icon: string;
  is_default: boolean;
  owned: boolean;
  active: boolean;
};

export type ShopResponse = {
  user: User;
  items: ShopItem[];
  message: string | null;
};

export type AdminQuestion = Question & {
  explanation: string;
  correct_answers: string[];
};

export type AdminQuestionPayload = {
  topic: string;
  type: "choice" | "input";
  prompt: string;
  explanation: string;
  placeholder: string | null;
  order_index: number;
  options: string[];
  correct_answers: string[];
};

export type QuestionDraft = {
  topic: string;
  type: "choice" | "input";
  prompt: string;
  explanation: string;
  placeholder: string;
  order_index: string;
  options_text: string;
  answers_text: string;
};
