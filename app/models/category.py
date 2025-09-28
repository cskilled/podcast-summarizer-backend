from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.episode import episode_categories_association


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)

    # Relationships
    episodes = relationship(
        "Episode",
        secondary=episode_categories_association,
        back_populates="categories",
        lazy="selectin"
    )