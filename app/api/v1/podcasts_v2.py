"""Updated Podcast API endpoints with PodcastIndex integration."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.podcast import Podcast
from app.models.episode import Episode
from app.models.summary import Summary
from app.models.category import Category
from app.services.podcastindex import PodcastIndexService
from app.services.summarizer import SummarizerService
from app.services.transcriber import TranscriberService

router = APIRouter(prefix="/api/v2/podcasts", tags=["podcasts_v2"])


@router.get("/trending")
async def get_trending_podcasts(
    max_results: int = Query(default=10, le=50),
    categories: Optional[str] = Query(default=None),
    lang: str = Query(default="en")
) -> List[Dict[str, Any]]:
    """
    Get trending podcasts from PodcastIndex.

    No authentication required - public endpoint.
    """
    service = PodcastIndexService()
    try:
        podcasts = await service.get_trending_podcasts(
            max_results=max_results,
            categories=categories,
            lang=lang
        )
        return podcasts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching trending podcasts: {str(e)}")


@router.get("/search")
async def search_podcasts(
    query: str = Query(..., min_length=1),
    max_results: int = Query(default=10, le=50)
) -> List[Dict[str, Any]]:
    """
    Search for podcasts using PodcastIndex.

    No authentication required - public endpoint.
    """
    service = PodcastIndexService()
    try:
        podcasts = await service.search_podcasts(
            query=query,
            max_results=max_results
        )
        return podcasts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching podcasts: {str(e)}")


@router.post("/subscribe/{podcast_index_id}")
async def subscribe_to_podcast(
    podcast_index_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Subscribe to a podcast and trigger summarization of last 3 episodes.
    """
    # Check if already subscribed
    result = await db.execute(
        select(Podcast).where(Podcast.podcast_index_id == podcast_index_id)
    )
    existing_podcast = result.scalar_one_or_none()

    if existing_podcast:
        # Check if user is already subscribed
        if current_user in existing_podcast.subscribers:
            return {
                "message": "Already subscribed to this podcast",
                "podcast_id": existing_podcast.id
            }
        # Add subscription
        existing_podcast.subscribers.append(current_user)
        await db.commit()

        # Trigger summarization for existing episodes
        background_tasks.add_task(
            summarize_recent_episodes,
            existing_podcast.id,
            db
        )

        return {
            "message": "Successfully subscribed to podcast",
            "podcast_id": existing_podcast.id
        }

    # Fetch podcast details from PodcastIndex
    service = PodcastIndexService()
    podcast_info = await service.get_podcast_by_id(podcast_index_id)

    if not podcast_info:
        raise HTTPException(status_code=404, detail="Podcast not found")

    # Create new podcast in database
    new_podcast = Podcast(
        title=podcast_info["title"],
        description=podcast_info.get("description", ""),
        rss_url=podcast_info["url"],
        podcast_index_id=podcast_index_id
    )
    new_podcast.subscribers.append(current_user)
    db.add(new_podcast)
    await db.commit()
    await db.refresh(new_podcast)

    # Fetch and store episodes, then summarize last 3
    background_tasks.add_task(
        fetch_and_summarize_episodes,
        new_podcast.id,
        podcast_index_id,
        db
    )

    return {
        "message": "Successfully subscribed to podcast",
        "podcast_id": new_podcast.id,
        "processing": "Episodes are being fetched and summarized"
    }


@router.get("/subscriptions")
async def get_user_subscriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get user's podcast subscriptions."""
    result = await db.execute(
        select(Podcast)
        .join(Podcast.subscribers)
        .where(User.id == current_user.id)
    )
    podcasts = result.scalars().all()

    return [
        {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "podcast_index_id": p.podcast_index_id,
            "created_at": p.created_at.isoformat() if p.created_at else None
        }
        for p in podcasts
    ]


@router.get("/{podcast_id}/episodes")
async def get_podcast_episodes(
    podcast_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get episodes for a subscribed podcast with summary status.
    """
    # Verify user is subscribed
    result = await db.execute(
        select(Podcast)
        .join(Podcast.subscribers)
        .where(Podcast.id == podcast_id, User.id == current_user.id)
    )
    podcast = result.scalar_one_or_none()

    if not podcast:
        raise HTTPException(status_code=403, detail="Not subscribed to this podcast")

    # Get episodes with summary status
    result = await db.execute(
        select(Episode)
        .where(Episode.podcast_id == podcast_id)
        .order_by(Episode.published_date.desc())
    )
    episodes = result.scalars().all()

    episode_list = []
    for episode in episodes:
        # Check if episode has summary
        summary_result = await db.execute(
            select(Summary).where(Summary.episode_id == episode.id)
        )
        has_summary = summary_result.scalar_one_or_none() is not None

        episode_list.append({
            "id": episode.id,
            "title": episode.title,
            "description": episode.description,
            "published_date": episode.published_date.isoformat() if episode.published_date else None,
            "duration_seconds": episode.duration_seconds,
            "has_summary": has_summary
        })

    return episode_list


@router.get("/episodes/{episode_id}/summary")
async def get_episode_summary(
    episode_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get summary for a specific episode.

    If summary doesn't exist, trigger generation.
    """
    # Verify user has access to this episode
    result = await db.execute(
        select(Episode)
        .join(Episode.podcast)
        .join(Podcast.subscribers)
        .where(Episode.id == episode_id, User.id == current_user.id)
    )
    episode = result.scalar_one_or_none()

    if not episode:
        raise HTTPException(status_code=403, detail="Access denied to this episode")

    # Check for existing summary
    result = await db.execute(
        select(Summary).where(Summary.episode_id == episode_id)
    )
    summary = result.scalar_one_or_none()

    if summary:
        # Get categories
        categories_result = await db.execute(
            select(Category)
            .join(Category.episodes)
            .where(Episode.id == episode_id)
        )
        categories = categories_result.scalars().all()

        return {
            "episode_id": episode_id,
            "title": episode.title,
            "summary": summary.summary_text,
            "categories": [c.name for c in categories],
            "created_at": summary.created_at.isoformat() if summary.created_at else None
        }

    # No summary exists, return pending status
    # In production, you might trigger background generation here
    return {
        "episode_id": episode_id,
        "title": episode.title,
        "summary": None,
        "status": "pending",
        "message": "Summary generation in progress"
    }


@router.post("/episodes/{episode_id}/summarize")
async def trigger_episode_summarization(
    episode_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Manually trigger summarization for an episode.
    """
    # Verify user has access
    result = await db.execute(
        select(Episode)
        .join(Episode.podcast)
        .join(Podcast.subscribers)
        .where(Episode.id == episode_id, User.id == current_user.id)
    )
    episode = result.scalar_one_or_none()

    if not episode:
        raise HTTPException(status_code=403, detail="Access denied to this episode")

    # Check if summary already exists
    result = await db.execute(
        select(Summary).where(Summary.episode_id == episode_id)
    )
    if result.scalar_one_or_none():
        return {"message": "Summary already exists"}

    # Trigger summarization
    background_tasks.add_task(
        summarize_single_episode,
        episode_id,
        db
    )

    return {"message": "Summarization triggered", "status": "processing"}


# Background task functions
async def fetch_and_summarize_episodes(
    podcast_id: int,
    podcast_index_id: int,
    db: AsyncSession
):
    """Fetch episodes from PodcastIndex and summarize the last 3."""
    try:
        service = PodcastIndexService()
        episodes_data = await service.get_episodes_by_podcast_id(podcast_index_id, max_results=10)

        # Store episodes in database
        for ep_data in episodes_data[:3]:  # Process only last 3
            # Check if episode exists
            result = await db.execute(
                select(Episode).where(
                    Episode.podcast_id == podcast_id,
                    Episode.title == ep_data["title"]
                )
            )
            existing = result.scalar_one_or_none()

            if not existing:
                # Handle published date - could be Unix timestamp or ISO string
                published = ep_data.get("published")
                if published:
                    if isinstance(published, int):
                        published_date = datetime.fromtimestamp(published)
                    else:
                        published_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
                else:
                    published_date = datetime.now()

                episode = Episode(
                    title=ep_data["title"],
                    description=ep_data.get("description", ""),
                    audio_url=ep_data["audio_url"],
                    published_date=published_date,
                    duration_seconds=ep_data.get("duration", 0),
                    podcast_id=podcast_id
                )
                db.add(episode)
                await db.commit()
                await db.refresh(episode)

                # Trigger summarization
                await summarize_single_episode(episode.id, db)
    except Exception as e:
        print(f"Error in fetch_and_summarize_episodes: {str(e)}")


async def summarize_recent_episodes(podcast_id: int, db: AsyncSession):
    """Summarize the 3 most recent episodes without summaries."""
    try:
        # Get recent episodes without summaries
        result = await db.execute(
            select(Episode)
            .outerjoin(Summary)
            .where(
                Episode.podcast_id == podcast_id,
                Summary.id.is_(None)
            )
            .order_by(Episode.published_date.desc())
            .limit(3)
        )
        episodes = result.scalars().all()

        for episode in episodes:
            await summarize_single_episode(episode.id, db)
    except Exception as e:
        print(f"Error in summarize_recent_episodes: {str(e)}")


async def summarize_single_episode(episode_id: int, db: AsyncSession):
    """Summarize a single episode."""
    try:
        # Get episode
        result = await db.execute(
            select(Episode).where(Episode.id == episode_id)
        )
        episode = result.scalar_one_or_none()

        if not episode:
            return

        # Initialize services
        transcriber = TranscriberService()
        summarizer = SummarizerService()

        # Transcribe
        transcript = await transcriber.transcribe_audio(
            episode.audio_url,
            episode.id
        )

        # Get categories
        result = await db.execute(select(Category))
        all_categories = result.scalars().all()
        available_categories = [c.name for c in all_categories]

        # Summarize
        summary_result = await summarizer.summarize_episode(
            transcript,
            available_categories
        )

        if summary_result:
            # Save summary
            summary = Summary(
                summary_text=summary_result["summary"],
                episode_id=episode_id
            )
            db.add(summary)

            # Add categories
            for cat_name in summary_result.get("categories", []):
                cat_result = await db.execute(
                    select(Category).where(Category.name == cat_name)
                )
                category = cat_result.scalar_one_or_none()
                if category and category not in episode.categories:
                    episode.categories.append(category)

            await db.commit()
    except Exception as e:
        print(f"Error summarizing episode {episode_id}: {str(e)}")