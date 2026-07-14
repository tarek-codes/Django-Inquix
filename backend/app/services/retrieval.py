from sqlalchemy import select
from app.database import async_session
from app.models import Chunk, Document
from app.services.embedding import get_embedding
from app.config import settings


async def retrieve_chunks(query: str, kb_id: str, top_k: int | None = None) -> list[dict]:
    if top_k is None:
        top_k = settings.top_k

    threshold = settings.similarity_threshold
    query_embedding = await get_embedding(query)

    async with async_session() as session:
        result = await session.execute(
            select(
                Chunk.id, Chunk.content, Chunk.chunk_index, Chunk.chunk_metadata,
                Document.filename, Document.source_type,
                (1 - Chunk.embedding.cosine_distance(query_embedding)).label("similarity"),
            )
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.kb_id == kb_id, Chunk.status == "active")
            .order_by(Chunk.embedding.cosine_distance(query_embedding))
            .limit(top_k * 2)
        )

        chunks = []
        for row in result:
            similarity = row.similarity
            if similarity is None or similarity < threshold:
                continue
            chunks.append({
                "id": str(row.id),
                "content": row.content,
                "chunk_index": row.chunk_index,
                "metadata": row.chunk_metadata or {},
                "filename": row.filename,
                "source_type": row.source_type,
                "similarity": round(similarity, 4),
            })

        return chunks[:top_k]
