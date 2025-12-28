"""
YouTube video transcription module.
Fetches captions via YouTubeTranscriptApi with Whisper fallback planned.
"""
from youtube_transcript_api import YouTubeTranscriptApi
from typing import List, Dict, Optional
import os
import json


def transcribe_youtube(video_id: str, cache_dir: str = "data/transcripts") -> str:
    """
    Fetch YouTube video transcript.
    
    Args:
        video_id: YouTube video ID (e.g., 't0k4WndiQxk')
        cache_dir: Directory to cache transcripts
        
    Returns:
        Full transcript text as a single string
        
    Raises:
        RuntimeError: If captions are unavailable and fallback not implemented
    """
    # Ensure cache directory exists
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{video_id}.json")
    
    # Check cache first
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            cached = json.load(f)
            return cached.get("text", "")
    
    try:
        # Fetch transcript with timestamps
        transcript_segments = YouTubeTranscriptApi.get_transcript(
            video_id, 
            languages=['en', 'en-US', 'en-GB']
        )
        
        # Build full text
        text = " ".join([seg['text'] for seg in transcript_segments])
        
        # Cache the result with metadata
        cache_data = {
            "video_id": video_id,
            "text": text,
            "segments": transcript_segments
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)
        
        return text
        
    except Exception as e:
        # TODO: Implement Whisper fallback for uncaptioned videos
        raise RuntimeError(f"Caption fetch failed for {video_id}: {e}")


def get_transcript_with_timestamps(video_id: str, cache_dir: str = "data/transcripts") -> List[Dict]:
    """
    Get transcript with timestamps for chunk metadata.
    
    Returns:
        List of segments with 'text', 'start', 'duration' keys
    """
    cache_file = os.path.join(cache_dir, f"{video_id}.json")
    
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            cached = json.load(f)
            return cached.get("segments", [])
    
    # If not cached, fetch and cache via transcribe_youtube
    transcribe_youtube(video_id, cache_dir)
    
    # Now read from cache
    with open(cache_file, 'r', encoding='utf-8') as f:
        cached = json.load(f)
        return cached.get("segments", [])
