import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.category import Category


DEFAULT_CATEGORIES = [
    "Technology",
    "Business",
    "Science",
    "Education",
    "Health & Wellness",
    "Arts & Culture",
    "Politics",
    "Sports",
    "Entertainment",
    "History",
    "Philosophy",
    "Psychology",
    "Economics",
    "Environment",
    "Social Issues",
    "Personal Development",
    "Comedy",
    "True Crime",
    "News & Current Affairs",
    "Music"
]


async def init_categories(db: AsyncSession):
    """Initialize default categories in the database."""
    for category_name in DEFAULT_CATEGORIES:
        # Check if category already exists
        result = await db.execute(select(Category).where(Category.name == category_name))
        existing_category = result.scalars().first()

        if not existing_category:
            new_category = Category(name=category_name)
            db.add(new_category)
            print(f"Added category: {category_name}")

    await db.commit()
    print("Categories initialized successfully!")


async def init_db():
    """Initialize database with default data."""
    async with AsyncSessionLocal() as db:
        await init_categories(db)


if __name__ == "__main__":
    asyncio.run(init_db())