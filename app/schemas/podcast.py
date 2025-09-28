from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import List, Optional


class PodcastBase(BaseModel):
    title: str
    description: Optional[str] = None
    rss_url: Optional[str] = None
    youtube_channel_id: Optional[str] = None


class PodcastCreate(BaseModel):
    url: str  # Can be RSS feed or YouTube channel URL


class PodcastResponse(PodcastBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EpisodeSummary(BaseModel):
    summary_text: str
    created_at: datetime

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class EpisodeResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    audio_url: str
    youtube_video_id: Optional[str] = None
    published_date: datetime
    duration_seconds: int
    podcast_id: int
    summary: Optional[EpisodeSummary] = None
    categories: List[CategoryResponse] = []

    class Config:
        from_attributes = True


class PodcastWithEpisodes(PodcastResponse):
    episodes: List[EpisodeResponse] = []


class RecommendationRequest(BaseModel):
    max_duration_minutes: int
    categories: Optional[List[str]] = None


class RecommendedEpisode(EpisodeResponse):
    podcast_title: str
    match_count: int