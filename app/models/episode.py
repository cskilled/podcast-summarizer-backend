from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

# Association table for episode-category relationships
episode_categories_association = Table(
    'episode_categories_association',
    Base.metadata,
    Column('episode_id', Integer, ForeignKey('episodes.id', ondelete='CASCADE'), primary_key=True),
    Column('category_id', Integer, ForeignKey('categories.id', ondelete='CASCADE'), primary_key=True)
)


class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    audio_url = Column(String, nullable=False)
    youtube_video_id = Column(String, index=True)
    published_date = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=False, index=True)
    podcast_id = Column(Integer, ForeignKey("podcasts.id", ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    podcast = relationship("Podcast", back_populates="episodes")
    summary = relationship("Summary", back_populates="episode", uselist=False, cascade="all, delete-orphan")
    categories = relationship(
        "Category",
        secondary=episode_categories_association,
        back_populates="episodes",
        lazy="selectin"
    )