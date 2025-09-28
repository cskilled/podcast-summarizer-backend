import feedparser
import httpx
from typing import Dict, Any
from datetime import datetime
from pytube import Channel, YouTube


class ScraperService:
    """Service for scraping podcast RSS feeds and YouTube channels."""

    @staticmethod
    def _parse_duration_from_itunes(duration_str: str) -> int:
        """Parse iTunes duration string to seconds."""
        try:
            # Format could be HH:MM:SS, MM:SS, or just seconds
            parts = duration_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            elif len(parts) == 2:
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            else:
                return int(duration_str)
        except:
            return 0

    @staticmethod
    async def scrape_rss_feed(rss_url: str, max_episodes: int = 3) -> Dict[str, Any]:
        """Scrape podcast information from RSS feed."""
        async with httpx.AsyncClient() as client:
            response = await client.get(rss_url)
            response.raise_for_status()

        feed = feedparser.parse(response.text)

        if not feed.entries:
            raise ValueError("No episodes found in RSS feed")

        # Extract podcast information
        podcast_info = {
            "title": feed.feed.get("title", "Unknown Podcast"),
            "description": feed.feed.get("description", ""),
            "rss_url": rss_url,
            "episodes": []
        }

        # Extract episode information (latest episodes)
        for entry in feed.entries[:max_episodes]:
            # Get audio URL from enclosures
            audio_url = None
            duration_seconds = 0

            for enclosure in entry.get("enclosures", []):
                if enclosure.get("type", "").startswith("audio/"):
                    audio_url = enclosure.get("href")
                    break

            # If no audio URL in enclosures, try links
            if not audio_url:
                for link in entry.get("links", []):
                    if link.get("type", "").startswith("audio/"):
                        audio_url = link.get("href")
                        break

            if not audio_url:
                continue  # Skip episodes without audio

            # Try to get duration from iTunes extension
            if hasattr(entry, "itunes_duration"):
                duration_seconds = ScraperService._parse_duration_from_itunes(entry.itunes_duration)

            # Parse published date
            published_date = datetime.now()
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published_date = datetime(*entry.published_parsed[:6])

            episode = {
                "title": entry.get("title", "Unknown Episode"),
                "description": entry.get("summary", ""),
                "audio_url": audio_url,
                "published_date": published_date,
                "duration_seconds": duration_seconds or 1800  # Default 30 minutes if unknown
            }

            podcast_info["episodes"].append(episode)

        return podcast_info

    @staticmethod
    async def scrape_youtube_channel(channel_url: str, max_episodes: int = 3) -> Dict[str, Any]:
        """Scrape podcast/video information from YouTube channel."""
        try:
            # Extract channel ID or handle from URL
            channel = Channel(channel_url)

            podcast_info = {
                "title": channel.channel_name,
                "description": f"YouTube Channel: {channel.channel_name}",
                "youtube_channel_id": channel.channel_id,
                "episodes": []
            }

            # Get latest videos
            video_urls = []
            for url in channel.video_urls:
                video_urls.append(url)
                if len(video_urls) >= max_episodes:
                    break

            # Extract video information
            for video_url in video_urls:
                try:
                    yt = YouTube(video_url)

                    # Parse duration
                    duration_seconds = yt.length or 0

                    episode = {
                        "title": yt.title,
                        "description": yt.description,
                        "audio_url": video_url,  # Store YouTube URL
                        "youtube_video_id": yt.video_id,
                        "published_date": yt.publish_date or datetime.now(),
                        "duration_seconds": duration_seconds
                    }

                    podcast_info["episodes"].append(episode)
                except Exception as e:
                    print(f"Error processing video {video_url}: {str(e)}")
                    continue

            return podcast_info

        except Exception as e:
            raise ValueError(f"Failed to scrape YouTube channel: {str(e)}")

    @staticmethod
    async def scrape_url(url: str, max_episodes: int = 3) -> Dict[str, Any]:
        """Automatically detect and scrape RSS feed or YouTube channel."""
        # Check if it's a YouTube URL
        if "youtube.com" in url or "youtu.be" in url:
            return await ScraperService.scrape_youtube_channel(url, max_episodes)
        else:
            # Assume it's an RSS feed
            return await ScraperService.scrape_rss_feed(url, max_episodes)