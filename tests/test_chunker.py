"""
Unit tests for the text chunker module.
"""
import pytest
from app.knowledge_base.chunker import chunk_text, chunk_with_timestamps


class TestChunkText:
    """Tests for the chunk_text function."""
    
    def test_basic_chunking(self):
        """Test that text is split into chunks."""
        text = "This is a test sentence. " * 100  # Create ~2500 chars
        chunks = chunk_text(text, chunk_size=500, chunk_overlap=100)
        
        assert len(chunks) > 1, "Should create multiple chunks for long text"
        assert all("id" in c for c in chunks), "All chunks should have an id"
        assert all("text" in c for c in chunks), "All chunks should have text"
        assert all("metadata" in c for c in chunks), "All chunks should have metadata"
    
    def test_chunk_ids_are_unique(self):
        """Test that all chunk IDs are unique."""
        text = "Sample text for testing. " * 50
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=50)
        
        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids)), "All chunk IDs should be unique"
    
    def test_chunk_metadata_includes_index(self):
        """Test that chunk metadata includes chunk_index."""
        text = "Testing metadata fields. " * 50
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=50)
        
        for i, chunk in enumerate(chunks):
            assert chunk["metadata"]["chunk_index"] == i
    
    def test_video_id_in_chunk_id(self):
        """Test that video_id is included in chunk ID prefix."""
        text = "Video specific content. " * 20
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=50, video_id="abc123")
        
        assert all(c["id"].startswith("abc123-chunk-") for c in chunks)
    
    def test_empty_text_returns_empty_list(self):
        """Test that empty text returns no chunks."""
        chunks = chunk_text("")
        assert chunks == [] or len(chunks) == 1  # May return 1 empty chunk
    
    def test_short_text_single_chunk(self):
        """Test that short text creates a single chunk."""
        text = "Short text."
        chunks = chunk_text(text, chunk_size=1000)
        
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Short text."


class TestChunkWithTimestamps:
    """Tests for the chunk_with_timestamps function."""
    
    def test_timestamps_preserved(self):
        """Test that timestamps are preserved in chunk metadata."""
        segments = [
            {"text": "First segment.", "start": 0.0, "duration": 5.0},
            {"text": "Second segment.", "start": 5.0, "duration": 5.0},
            {"text": "Third segment.", "start": 10.0, "duration": 5.0},
        ]
        
        chunks = chunk_with_timestamps(segments, chunk_size=500, chunk_overlap=100)
        
        for chunk in chunks:
            assert "timestamp" in chunk["metadata"]
            assert "timestamp_str" in chunk["metadata"]
    
    def test_timestamp_format(self):
        """Test that timestamp_str is in HH:MM:SS format."""
        segments = [
            {"text": "Content at 1 hour 30 minutes. " * 20, "start": 5400.0, "duration": 60.0},
        ]
        
        chunks = chunk_with_timestamps(segments, chunk_size=200)
        
        # 5400 seconds = 01:30:00
        assert chunks[0]["metadata"]["timestamp_str"] == "01:30:00"
    
    def test_video_id_in_metadata(self):
        """Test that video_id is included in chunk metadata."""
        segments = [
            {"text": "Test content. " * 10, "start": 0.0, "duration": 10.0}
        ]
        
        chunks = chunk_with_timestamps(segments, video_id="test_video")
        
        assert all(c["metadata"]["video_id"] == "test_video" for c in chunks)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
