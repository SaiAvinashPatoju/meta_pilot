"""
Text chunking module for semantic splitting.
Uses LangChain's RecursiveCharacterTextSplitter with tiktoken encoding.
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List, Dict, Optional
import hashlib


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    video_id: Optional[str] = None
) -> List[Dict]:
    """
    Split text into semantic chunks with metadata.
    
    Args:
        text: Full transcript text
        chunk_size: Target chunk size in tokens
        chunk_overlap: Overlap between chunks
        video_id: Optional video ID for chunk IDs
        
    Returns:
        List of chunk dictionaries with id, text, and metadata
    """
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",  # GPT-4 encoding
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    docs = splitter.split_text(text)
    
    chunks = []
    prefix = video_id or "doc"
    
    for i, doc_text in enumerate(docs):
        # Create unique chunk ID
        content_hash = hashlib.md5(doc_text.encode()).hexdigest()[:8]
        chunk_id = f"{prefix}-chunk-{i:04d}-{content_hash}"
        
        chunks.append({
            "id": chunk_id,
            "text": doc_text,
            "metadata": {
                "chunk_index": i,
                "video_id": video_id,
                "char_count": len(doc_text),
                "text": doc_text  # Store text in metadata for retrieval
            }
        })
    
    return chunks


def chunk_with_timestamps(
    segments: List[Dict],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    video_id: Optional[str] = None
) -> List[Dict]:
    """
    Chunk transcript while preserving timestamp information.
    
    Args:
        segments: List of transcript segments with 'text', 'start', 'duration'
        chunk_size: Target chunk size in tokens
        chunk_overlap: Overlap between chunks
        video_id: Optional video ID for chunk IDs
        
    Returns:
        List of chunks with timestamp metadata
    """
    # Build full text with position tracking
    full_text = ""
    position_to_timestamp = []
    
    for seg in segments:
        start_pos = len(full_text)
        seg_text = seg['text'] + " "
        full_text += seg_text
        position_to_timestamp.append({
            "start_pos": start_pos,
            "end_pos": len(full_text),
            "timestamp": seg.get('start', 0)
        })
    
    # Split into chunks
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    docs = splitter.split_text(full_text)
    
    chunks = []
    prefix = video_id or "doc"
    current_pos = 0
    
    for i, doc_text in enumerate(docs):
        # Find approximate timestamp for this chunk
        chunk_start_pos = full_text.find(doc_text, current_pos)
        if chunk_start_pos == -1:
            chunk_start_pos = current_pos
        
        # Find the timestamp closest to chunk start
        timestamp = 0
        for pt in position_to_timestamp:
            if pt["start_pos"] <= chunk_start_pos < pt["end_pos"]:
                timestamp = pt["timestamp"]
                break
            elif pt["start_pos"] > chunk_start_pos:
                break
            timestamp = pt["timestamp"]
        
        content_hash = hashlib.md5(doc_text.encode()).hexdigest()[:8]
        chunk_id = f"{prefix}-chunk-{i:04d}-{content_hash}"
        
        # Format timestamp as HH:MM:SS
        hours = int(timestamp // 3600)
        minutes = int((timestamp % 3600) // 60)
        seconds = int(timestamp % 60)
        timestamp_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        chunks.append({
            "id": chunk_id,
            "text": doc_text,
            "metadata": {
                "chunk_index": i,
                "video_id": video_id,
                "timestamp": timestamp,
                "timestamp_str": timestamp_str,
                "char_count": len(doc_text),
                "text": doc_text
            }
        })
        
        current_pos = chunk_start_pos + len(doc_text) - chunk_overlap
    
    return chunks
