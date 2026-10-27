from uuid import UUID

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    user_id: UUID
    display_name: str | None
    total_points: int
    challenges_completed: int
    rank: int


class TeamLeaderboardEntry(BaseModel):
    team_id: UUID
    team_name: str
    total_points: int
    members: int
    rank: int
