from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.user import user_podcasts_association


class Podcast(Base):
    __tablename__ = "podcasts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    rss_url = Column(String, unique=True, nullable=False, index=True)
    podcast_index_id = Column(Integer, unique=True, index=True)  # Store PodcastIndex ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    episodes = relationship("Episode", back_populates="podcast", cascade="all, delete-orphan")
    subscribers = relationship(
        "User",
        secondary=user_podcasts_association,
        back_populates="subscribed_podcasts",
        lazy="selectin"
    )