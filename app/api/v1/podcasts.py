from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Podcast, Episode, Summary, Category
from app.models.user import user_podcasts_association
from app.schemas.podcast import (
    PodcastCreate,
    PodcastResponse,
    PodcastWithEpisodes,
    EpisodeResponse,
    RecommendedEpisode
)
from app.services.scraper import ScraperService
from app.services.transcriber import TranscriberService
from app.services.summarizer import SummarizerService
from app.services.recommender import RecommenderService
from app.core.config import settings

router = APIRouter()


async def process_podcast_ingestion(
    url: str,
    user_id: int,
    db_session_factory
):
    """Background task to process podcast ingestion."""
    async with db_session_factory() as db:
        try:
            # Initialize services
            scraper = ScraperService()
            transcriber = TranscriberService()
            summarizer = SummarizerService()

            # Scrape podcast data
            podcast_data = await scraper.scrape_url(url, settings.MAX_EPISODES_PER_PODCAST)

            # Check if podcast exists
            if podcast_data.get("rss_url"):
                result = await db.execute(
                    select(Podcast).where(Podcast.rss_url == podcast_data["rss_url"])
                )
            elif podcast_data.get("youtube_channel_id"):
                result = await db.execute(
                    select(Podcast).where(Podcast.youtube_channel_id == podcast_data["youtube_channel_id"])
                )
            else:
                raise ValueError("No valid podcast identifier found")

            podcast = result.scalars().first()

            # Create podcast if it doesn't exist
            if not podcast:
                podcast = Podcast(
                    title=podcast_data["title"],
                    description=podcast_data.get("description", ""),
                    rss_url=podcast_data.get("rss_url"),
                    youtube_channel_id=podcast_data.get("youtube_channel_id")
                )
                db.add(podcast)
                await db.flush()

            # Subscribe user to podcast
            user = await db.get(User, user_id)
            if podcast not in user.subscribed_podcasts:
                user.subscribed_podcasts.append(podcast)

            # Get all available categories
            category_result = await db.execute(select(Category))
            available_categories = [cat.name for cat in category_result.scalars().all()]

            # Process episodes
            for episode_data in podcast_data["episodes"]:
                # Check if episode already exists
                episode_result = await db.execute(
                    select(Episode).where(
                        Episode.podcast_id == podcast.id,
                        Episode.title == episode_data["title"]
                    )
                )
                episode = episode_result.scalars().first()

                if not episode:
                    # Create new episode
                    episode = Episode(
                        title=episode_data["title"],
                        description=episode_data.get("description", ""),
                        audio_url=episode_data["audio_url"],
                        youtube_video_id=episode_data.get("youtube_video_id"),
                        published_date=episode_data["published_date"],
                        duration_seconds=episode_data["duration_seconds"],
                        podcast_id=podcast.id
                    )
                    db.add(episode)
                    await db.flush()

                    # Transcribe the episode
                    transcript = await transcriber.transcribe_audio(
                        episode_data["audio_url"],
                        episode.id,
                        episode_data.get("youtube_video_id")
                    )

                    # Generate summary and categorization
                    summary_data = await summarizer.summarize_episode(
                        transcript,
                        available_categories
                    )

                    # Create summary
                    summary = Summary(
                        summary_text=summary_data["summary"],
                        episode_id=episode.id
                    )
                    db.add(summary)

                    # Add categories
                    for category_name in summary_data["categories"]:
                        category_result = await db.execute(
                            select(Category).where(Category.name == category_name)
                        )
                        category = category_result.scalars().first()
                        if category:
                            # Use a direct query to add the category association
                            from sqlalchemy import text
                            await db.execute(
                                text("INSERT INTO episode_categories_association (episode_id, category_id) "
                                     "VALUES (:episode_id, :category_id) "
                                     "ON CONFLICT DO NOTHING"),
                                {"episode_id": episode.id, "category_id": category.id}
                            )

            await db.commit()

        except Exception as e:
            print(f"Error processing podcast: {str(e)}")
            await db.rollback()
            raise


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_podcast(
    podcast_data: PodcastCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Ingest a new podcast from URL (RSS feed or YouTube channel)."""
    # Add background task for processing
    from app.core.database import AsyncSessionLocal
    background_tasks.add_task(
        process_podcast_ingestion,
        podcast_data.url,
        current_user.id,
        AsyncSessionLocal
    )

    return {
        "message": "Podcast ingestion started",
        "status": "processing"
    }


@router.get("/subscriptions", response_model=List[PodcastResponse])
async def get_subscriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of podcasts the current user is subscribed to."""
    # Refresh user to load subscriptions
    await db.refresh(current_user, ['subscribed_podcasts'])
    return current_user.subscribed_podcasts


@router.post("/{podcast_id}/subscribe", response_model=dict)
async def subscribe_to_podcast(
    podcast_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Subscribe the user to an existing podcast."""
    podcast = await db.get(Podcast, podcast_id)
    if not podcast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Podcast not found"
        )

    await db.refresh(current_user, ['subscribed_podcasts'])

    if podcast in current_user.subscribed_podcasts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already subscribed to this podcast"
        )

    current_user.subscribed_podcasts.append(podcast)
    await db.commit()

    return {"message": "Successfully subscribed to podcast"}


@router.delete("/{podcast_id}/unsubscribe", response_model=dict)
async def unsubscribe_from_podcast(
    podcast_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Unsubscribe the user from a podcast."""
    podcast = await db.get(Podcast, podcast_id)
    if not podcast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Podcast not found"
        )

    await db.refresh(current_user, ['subscribed_podcasts'])

    if podcast not in current_user.subscribed_podcasts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not subscribed to this podcast"
        )

    current_user.subscribed_podcasts.remove(podcast)
    await db.commit()

    return {"message": "Successfully unsubscribed from podcast"}


@router.get("/{podcast_id}/episodes", response_model=List[EpisodeResponse])
async def get_podcast_episodes(
    podcast_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all processed episodes for a podcast the user is subscribed to."""
    # Check if user is subscribed to the podcast
    await db.refresh(current_user, ['subscribed_podcasts'])
    podcast = await db.get(Podcast, podcast_id)

    if not podcast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Podcast not found"
        )

    if podcast not in current_user.subscribed_podcasts:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not subscribed to this podcast"
        )

    # Get episodes with summaries and categories
    result = await db.execute(
        select(Episode)
        .where(Episode.podcast_id == podcast_id)
        .order_by(Episode.published_date.desc())
    )
    episodes = result.scalars().all()

    # Load relationships for each episode
    for episode in episodes:
        await db.refresh(episode, ['summary', 'categories'])

    return episodes


@router.get("/recommendations", response_model=List[RecommendedEpisode])
async def get_recommendations(
    max_duration_minutes: int = Query(..., description="Maximum duration in minutes"),
    categories: Optional[List[str]] = Query(None, description="Preferred categories"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get ranked list of recommended episodes based on user preferences."""
    recommender = RecommenderService()

    # If no categories provided, get user's preferred categories
    if not categories:
        categories = await recommender.get_user_preferred_categories(db, current_user.id)

    # Convert minutes to seconds
    max_duration_seconds = max_duration_minutes * 60

    # Get recommendations
    recommendations = await recommender.get_recommendations(
        db,
        categories,
        max_duration_seconds
    )

    return recommendations