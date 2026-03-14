import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from models import Chunk
from config import EMBEDDING_MODEL


class EmbeddingIndex:
    def __init__(self):
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self.index = None
        self.chunks: list[Chunk] = []
        self.dimension = None

    def build_index(self, chunks: list[Chunk]):
        self.chunks = chunks
        
        if not chunks:
            print("Warning: No chunks to index")
            self.index = None
            return
        
        texts = [chunk.text for chunk in chunks]
        
        # Filter out empty texts
        valid_chunks = []
        valid_texts = []
        for chunk, text in zip(chunks, texts):
            if text and text.strip():
                valid_chunks.append(chunk)
                valid_texts.append(text)
        
        if not valid_texts:
            print("Warning: All chunks have empty text")
            self.chunks = []
            self.index = None
            return
        
        self.chunks = valid_chunks
        
        print(f"Building index with {len(valid_texts)} chunks...")
        embeddings = self.model.encode(valid_texts, convert_to_numpy=True)
        embeddings = np.array(embeddings).astype("float32")
        
        # Handle case where embeddings might be 1D (single chunk)
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)
        
        self.dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(embeddings)
        print(f"Index built successfully with dimension {self.dimension}")

    def search(self, query: str, top_k: int = 5) -> list[Chunk]:
        if self.index is None or len(self.chunks) == 0:
            return []
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        query_embedding = np.array(query_embedding).astype("float32")
        
        # Handle 1D embedding
        if len(query_embedding.shape) == 1:
            query_embedding = query_embedding.reshape(1, -1)
            
        distances, indices = self.index.search(query_embedding, min(top_k, len(self.chunks)))
        results = []
        for idx in indices[0]:
            if idx >= 0 and idx < len(self.chunks):
                results.append(self.chunks[idx])
        return results

    def get_all_chunks(self) -> list[Chunk]:
        return self.chunks
