"""
Pinecone vector store integration.
Handles embeddings via OpenAI and vector upsert/query.
"""
import os
from typing import List, Dict, Optional
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI
from app.config import settings


class VectorStore:
    """Wrapper around Pinecone for embedding storage and retrieval."""
    
    def __init__(self):
        """Initialize Pinecone client and OpenAI embeddings."""
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index_name = settings.pinecone_index_name
        self.embed_client = OpenAI(api_key=settings.openai_api_key)
        self.embedding_model = settings.embedding_model
        
        # Ensure index exists
        self._ensure_index()
        self.index = self.pc.Index(self.index_name)
    
    def _ensure_index(self):
        """Create index if it doesn't exist."""
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]
        
        if self.index_name not in existing_indexes:
            # Create serverless index (free tier compatible)
            self.pc.create_index(
                name=self.index_name,
                dimension=1536,  # text-embedding-3-small dimension
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        # OpenAI has a limit of 8191 tokens per request, batch if needed
        batch_size = 100
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.embed_client.embeddings.create(
                model=self.embedding_model,
                input=batch
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    def upsert_chunks(self, video_id: str, chunks: List[Dict]) -> Dict:
        """
        Upsert text chunks to Pinecone.
        
        Args:
            video_id: Source video identifier
            chunks: List of chunk dictionaries with id, text, metadata
            
        Returns:
            Upsert response with count
        """
        texts = [c["text"] for c in chunks]
        embeddings = self.embed(texts)
        
        vectors = []
        for chunk, emb in zip(chunks, embeddings):
            # Prepare metadata (Pinecone has size limits)
            metadata = {
                "video_id": video_id,
                "chunk_index": chunk["metadata"].get("chunk_index", 0),
                "timestamp": chunk["metadata"].get("timestamp", 0),
                "timestamp_str": chunk["metadata"].get("timestamp_str", "00:00:00"),
                # Store truncated text in metadata for retrieval
                "text": chunk["text"][:1000] if len(chunk["text"]) > 1000 else chunk["text"]
            }
            vectors.append({
                "id": chunk["id"],
                "values": emb,
                "metadata": metadata
            })
        
        # Upsert in batches
        batch_size = 100
        total_upserted = 0
        
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch)
            total_upserted += len(batch)
        
        return {"upserted": total_upserted, "video_id": video_id}
    
    def query(self, query_text: str, top_k: int = 4, filter: Optional[Dict] = None) -> List[Dict]:
        """
        Query vector store for similar chunks.
        
        Args:
            query_text: Query string
            top_k: Number of results to return
            filter: Optional metadata filter
            
        Returns:
            List of matching chunks with scores
        """
        query_embedding = self.embed([query_text])[0]
        
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            include_values=False,
            filter=filter
        )
        
        matches = []
        for match in results.matches:
            matches.append({
                "id": match.id,
                "score": match.score,
                "metadata": match.metadata,
                "text": match.metadata.get("text", "")
            })
        
        return matches
    
    def delete_by_video(self, video_id: str) -> Dict:
        """Delete all chunks for a specific video."""
        # Pinecone serverless uses filter-based deletion
        self.index.delete(filter={"video_id": video_id})
        return {"deleted": True, "video_id": video_id}
