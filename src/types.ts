export type User = {
  id: number;
  username: string;
  is_admin: boolean;
};

export type Question = {
  id: number;
  topic: string;
  type: "choice" | "input";
  prompt: string;
  options: string[];
  placeholder: string | null;
  order_index: number;
};

export type Progress = {
  topic: string;
  current_index: number;
  current_score: number;
  best_score: number;
  completed_runs: number;
  total_questions: number;
  next_question_id: number | null;
};

export type BootstrapResponse = {
  user: User;
  questions: Question[];
  progress: Progress;
};

export type Credentials = {
  username: string;
  password: string;
};

export type AuthResponse = {
  token: string;
  user: User;
};

export type SubmitAnswerPayload = {
  topic: string;
  question_id: number;
  answer: string;
};

export type AnswerResult = {
  is_correct: boolean;
  correct_answers: string[];
  explanation: string;
  next_progress: Progress;
  quiz_completed: boolean;
  final_score: number | null;
  total_questions: number;
};

export type LeaderboardEntry = {
  rank: number;
  username: string;
  best_score: number;
  completed_runs: number;
  last_played_at: string | null;
};

export type LeaderboardResponse = {
  topic: string;
  entries: LeaderboardEntry[];
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
