from typing import List, Optional

from pydantic import BaseModel, Field


class CredentialsIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class QuestionOut(BaseModel):
    id: int
    topic: str
    type: str
    prompt: str
    options: List[str] = []
    placeholder: Optional[str] = None
    order_index: int


class ProgressOut(BaseModel):
    topic: str
    current_index: int
    current_score: int
    best_score: int
    completed_runs: int
    total_questions: int
    next_question_id: Optional[int] = None


class BootstrapResponse(BaseModel):
    user: UserOut
    questions: List[QuestionOut]
    progress: ProgressOut


class SubmitAnswerIn(BaseModel):
    topic: str = Field(..., min_length=1, max_length=50)
    question_id: int
    answer: str = Field(..., min_length=1, max_length=500)


class AnswerResponse(BaseModel):
    is_correct: bool
    correct_answers: List[str]
    explanation: str
    next_progress: ProgressOut
    quiz_completed: bool
    final_score: Optional[int] = None
    total_questions: int


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    best_score: int
    completed_runs: int
    last_played_at: Optional[str] = None


class LeaderboardResponse(BaseModel):
    topic: str
    entries: List[LeaderboardEntry]


class AdminQuestionIn(BaseModel):
    topic: str = Field(..., min_length=1, max_length=50)
    type: str = Field(..., min_length=1, max_length=20)
    prompt: str = Field(..., min_length=5, max_length=500)
    explanation: str = Field(..., min_length=3, max_length=500)
    placeholder: Optional[str] = Field(default=None, max_length=120)
    order_index: int = 0
    options: List[str] = []
    correct_answers: List[str] = []


class AdminQuestionOut(QuestionOut):
    explanation: str
    correct_answers: List[str]
