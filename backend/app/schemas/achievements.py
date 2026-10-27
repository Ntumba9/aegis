from datetime import datetime

from pydantic import BaseModel


class AchievementOut(BaseModel):
    id: str
    title: str
    description: str
    icon: str


class EarnedAchievementOut(BaseModel):
    achievement_id: str
    title: str
    description: str
    icon: str
    earned_at: datetime
