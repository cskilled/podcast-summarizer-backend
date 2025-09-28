from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional

from app.models import Episode, Category, Podcast
from app.models.episode import episode_categories_association


class RecommenderService:
    """Service for generating episode recommendations based on user preferences."""

    @staticmethod
    async def get_recommendations(
        db: AsyncSession,
        preferred_categories: List[str],
        max_duration_seconds: int,
        limit: int = 20
    ) -> List[dict]:
        """
        Get recommended episodes using a tiered ranking strategy.

        The ranking is based on:
        1. Number of matching categories (primary)
        2. Duration (secondary - shorter is better)
        3. Published date (tertiary - newer is better)
        """

        # Get category IDs from names
        category_result = await db.execute(
            select(Category).where(Category.name.in_(preferred_categories))
        )
        categories = category_result.scalars().all()
        category_ids = [cat.id for cat in categories]

        if not category_ids:
            # If no valid categories, return empty list
            return []

        # Build the main query with tiered ranking
        # Count how many preferred categories each episode matches
        match_count_subquery = (
            select(
                episode_categories_association.c.episode_id,
                func.count(episode_categories_association.c.category_id).label('match_count')
            )
            .where(episode_categories_association.c.category_id.in_(category_ids))
            .group_by(episode_categories_association.c.episode_id)
            .subquery()
        )

        # Main query to get recommended episodes
        query = (
            select(
                Episode,
                Podcast.title.label('podcast_title'),
                match_count_subquery.c.match_count
            )
            .join(Podcast, Episode.podcast_id == Podcast.id)
            .join(match_count_subquery, Episode.id == match_count_subquery.c.episode_id)
            .where(Episode.duration_seconds <= max_duration_seconds)
            .order_by(
                match_count_subquery.c.match_count.desc(),  # Most matches first
                Episode.duration_seconds.asc(),              # Shorter episodes next
                Episode.published_date.desc()                # Newest episodes last
            )
            .limit(limit)
        )

        result = await db.execute(query)
        recommendations = []

        for row in result:
            episode = row.Episode
            podcast_title = row.podcast_title
            match_count = row.match_count

            # Load relationships
            await db.refresh(episode, ['summary', 'categories'])

            recommendation = {
                "id": episode.id,
                "title": episode.title,
                "description": episode.description,
                "audio_url": episode.audio_url,
                "youtube_video_id": episode.youtube_video_id,
                "published_date": episode.published_date,
                "duration_seconds": episode.duration_seconds,
                "podcast_id": episode.podcast_id,
                "podcast_title": podcast_title,
                "match_count": match_count,
                "summary": {
                    "summary_text": episode.summary.summary_text if episode.summary else None,
                    "created_at": episode.summary.created_at if episode.summary else None
                } if episode.summary else None,
                "categories": [
                    {"id": cat.id, "name": cat.name}
                    for cat in episode.categories
                ]
            }

            recommendations.append(recommendation)

        return recommendations

    @staticmethod
    async def get_user_preferred_categories(
        db: AsyncSession,
        user_id: int
    ) -> List[str]:
        """
        Get user's preferred categories based on their subscription history.
        This could be enhanced to track actual user preferences or analyze
        their listening history.
        """
        # For MVP, we'll return a default set of categories or extract from
        # user's subscribed podcasts' episodes
        # This is a placeholder for more sophisticated preference tracking

        # Get categories from user's subscribed podcasts
        query = (
            select(Category.name)
            .distinct()
            .join(episode_categories_association, Category.id == episode_categories_association.c.category_id)
            .join(Episode, Episode.id == episode_categories_association.c.episode_id)
            .join(Podcast, Podcast.id == Episode.podcast_id)
            .where(
                Podcast.id.in_(
                    select(Podcast.id)
                    .join(Podcast.subscribers)
                    .where(Podcast.subscribers.any(id=user_id))
                )
            )
        )

        result = await db.execute(query)
        categories = [row[0] for row in result]

        # If user has no history, return some default categories
        if not categories:
            categories = ["Technology", "Business", "Science", "Education"]

        return categories