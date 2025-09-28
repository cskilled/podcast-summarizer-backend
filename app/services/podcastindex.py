"""PodcastIndex API integration service."""

import hashlib
import time
import httpx
from typing import List, Dict, Any, Optional
from app.core.config import settings


class PodcastIndexService:
    """Service for interacting with PodcastIndex API."""

    def __init__(self):
        """Initialize PodcastIndex service."""
        self.api_key = settings.PODCASTINDEX_API_KEY
        self.api_secret = settings.PODCASTINDEX_API_SECRET
        self.base_url = "https://api.podcastindex.org/api/1.0"

    def _get_auth_headers(self) -> Dict[str, str]:
        """Generate authentication headers for PodcastIndex API."""
        if not self.api_key or not self.api_secret:
            raise ValueError("PodcastIndex API credentials not configured")

        # Generate auth headers according to PodcastIndex requirements
        epoch_time = str(int(time.time()))
        data_to_hash = self.api_key + self.api_secret + epoch_time
        sha1_hash = hashlib.sha1(data_to_hash.encode()).hexdigest()

        return {
            "X-Auth-Date": epoch_time,
            "X-Auth-Key": self.api_key,
            "Authorization": sha1_hash,
            "User-Agent": "PodcastSummarizer/1.0"
        }

    async def get_trending_podcasts(
        self,
        max_results: int = 10,
        categories: Optional[str] = None,
        lang: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Get trending podcasts from PodcastIndex.

        Args:
            max_results: Maximum number of results to return
            categories: Comma-separated category IDs (optional)
            lang: Language code (default: "en")

        Returns:
            List of trending podcasts
        """
        async with httpx.AsyncClient() as client:
            params = {
                "max": max_results,
                "lang": lang
            }
            if categories:
                params["cat"] = categories

            response = await client.get(
                f"{self.base_url}/podcasts/trending",
                headers=self._get_auth_headers(),
                params=params
            )
            response.raise_for_status()
            data = response.json()

            # Transform the response to our format
            podcasts = []
            for feed in data.get("feeds", []):
                podcasts.append({
                    "id": feed.get("id"),
                    "title": feed.get("title"),
                    "description": feed.get("description"),
                    "url": feed.get("url"),  # RSS feed URL
                    "image": feed.get("image"),
                    "categories": feed.get("categories", {}),
                    "author": feed.get("author"),
                    "episode_count": feed.get("episodeCount", 0),
                    "latest_publish": feed.get("newestItemPubdate")
                })

            return podcasts

    async def search_podcasts(
        self,
        query: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for podcasts by query.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of matching podcasts
        """
        async with httpx.AsyncClient() as client:
            params = {
                "q": query,
                "max": max_results
            }

            response = await client.get(
                f"{self.base_url}/search/byterm",
                headers=self._get_auth_headers(),
                params=params
            )
            response.raise_for_status()
            data = response.json()

            # Transform the response
            podcasts = []
            for feed in data.get("feeds", []):
                podcasts.append({
                    "id": feed.get("id"),
                    "title": feed.get("title"),
                    "description": feed.get("description"),
                    "url": feed.get("url"),
                    "image": feed.get("image"),
                    "categories": feed.get("categories", {}),
                    "author": feed.get("author"),
                    "episode_count": feed.get("episodeCount", 0)
                })

            return podcasts

    async def get_podcast_by_id(
        self,
        podcast_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get podcast details by PodcastIndex ID.

        Args:
            podcast_id: PodcastIndex podcast ID

        Returns:
            Podcast details or None if not found
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/podcasts/byfeedid",
                headers=self._get_auth_headers(),
                params={"id": podcast_id}
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            feed = data.get("feed")
            if not feed:
                return None

            return {
                "id": feed.get("id"),
                "title": feed.get("title"),
                "description": feed.get("description"),
                "url": feed.get("url"),
                "image": feed.get("image"),
                "categories": feed.get("categories", {}),
                "author": feed.get("author"),
                "episode_count": feed.get("episodeCount", 0)
            }

    async def get_episodes_by_podcast_id(
        self,
        podcast_id: int,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get episodes for a specific podcast.

        Args:
            podcast_id: PodcastIndex podcast ID
            max_results: Maximum number of episodes

        Returns:
            List of episodes
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/episodes/byfeedid",
                headers=self._get_auth_headers(),
                params={
                    "id": podcast_id,
                    "max": max_results
                }
            )
            response.raise_for_status()
            data = response.json()

            episodes = []
            for item in data.get("items", []):
                episodes.append({
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "description": item.get("description"),
                    "audio_url": item.get("enclosureUrl"),
                    "duration": item.get("duration", 0),
                    "published": item.get("datePublished"),
                    "episode_type": item.get("episodeType"),
                    "season": item.get("season"),
                    "episode": item.get("episode")
                })

            return episodes