from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base

# Association table for user-podcast subscriptions
user_podcasts_association = Table(
    'user_podcasts_association',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('podcast_id', Integer, ForeignKey('podcasts.id', ondelete='CASCADE'), primary_key=True)
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    # Relationships
    subscribed_podcasts = relationship(
        "Podcast",
        secondary=user_podcasts_association,
        back_populates="subscribers",
        lazy="selectin"
    )