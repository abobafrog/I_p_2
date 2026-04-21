from typing import List, Optional

from pydantic import BaseModel, Field


class CredentialsIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=37)
    password: str = Field(..., min_length=6, max_length=128)


class ProfileUpdateIn(BaseModel):
    display_name: str = Field(..., min_length=3, max_length=32)
    current_password: Optional[str] = Field(default=None, max_length=128)
    new_password: Optional[str] = Field(default=None, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    tag: Optional[str] = None
    full_username: str
    is_admin: bool
    coins: int
    inventory: List[str]
    active_skin: str
    active_skin_label: str
    active_skin_icon: str


class AuthResponse(BaseModel):
    user: UserOut
    csrf_token: str


class SessionOut(AuthResponse):
    pass


class QuestionOut(BaseModel):
    id: int
    topic: str
    language: str
    difficulty: str
    level_index: int
    task_index: int
    type: str
    prompt: str
    options: List[str] = []
    placeholder: Optional[str] = None
    hint: str
    order_index: int


class ProgressOut(BaseModel):
    topic: str
    current_index: int
    current_score: int
    opened_questions: int
    best_score: int
    completed_runs: int
    remaining_hearts: int
    total_questions: int
    levels_total: int
    tasks_per_level: int
    current_level_index: int
    current_task_index: int
    unlocked_level_index: int
    next_question_id: Optional[int] = None


class BootstrapResponse(BaseModel):
    user: UserOut
    questions: List[QuestionOut]
    progress: ProgressOut


class ProgressListResponse(BaseModel):
    items: List[ProgressOut]


class RouteOut(BaseModel):
    topic: str
    language: str
    difficulty: str
    difficulty_label: str
    levels_total: int
    questions_total: int
    tasks_per_level: int


class RouteListResponse(BaseModel):
    items: List[RouteOut]


class SubmitAnswerIn(BaseModel):
    topic: str = Field(..., min_length=1, max_length=50)
    question_id: int
    answer: str = Field(..., min_length=1, max_length=500)


class TopicIn(BaseModel):
    topic: str = Field(..., min_length=1, max_length=50)


class SelectLevelIn(TopicIn):
    level_index: int = Field(..., ge=0, le=20)


class PromoRedeemIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)


class AnswerResponse(BaseModel):
    is_correct: bool
    correct_answers: List[str]
    explanation: str
    next_progress: ProgressOut
    user: UserOut
    coins_awarded: int
    quiz_completed: bool
    final_score: Optional[int] = None
    total_questions: int


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    tag: Optional[str] = None
    full_username: str
    metric_value: int
    best_score: int
    completed_runs: int
    coins: int
    last_played_at: Optional[str] = None


class LeaderboardResponse(BaseModel):
    topic: str
    metric: str
    metric_label: str
    scope: str
    entries: List[LeaderboardEntry]


class ShopItemOut(BaseModel):
    id: str
    name: str
    description: str
    price: int
    icon: str
    is_default: bool
    owned: bool
    active: bool


class ShopResponse(BaseModel):
    user: UserOut
    items: List[ShopItemOut]
    message: Optional[str] = None


class PromoRedeemResponse(BaseModel):
    user: UserOut
    progresses: List[ProgressOut]
    message: str


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
