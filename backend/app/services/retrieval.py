from asgiref.sync import sync_to_async
from pgvector.django import CosineDistance
from app.models import Chunk
from app.services.embedding import get_embedding
from app.config import settings


async def retrieve_chunks(query: str, kb_id: str, top_k: int | None = None) -> list[dict]:
    if top_k is None:
        top_k = settings.top_k

    threshold = settings.similarity_threshold
    query_embedding = await get_embedding(query)

    def _query_db():
        chunks_qs = Chunk.objects.filter(kb_id=kb_id, status="active", document__status="ready") \
            .annotate(distance=CosineDistance('embedding', query_embedding)) \
            .select_related('document') \
            .order_by('distance')[:top_k * 2]

        chunks = []
        for row in chunks_qs:
            distance = row.distance
            if distance is None:
                continue
            similarity = 1 - distance
            if similarity < threshold:
                continue
            chunks.append({
                "id": str(row.id),
                "content": row.content,
                "chunk_index": row.chunk_index,
                "metadata": row.chunk_metadata or {},
                "filename": row.document.filename,
                "source_type": row.document.source_type,
                "similarity": round(similarity, 4),
            })
        return chunks[:top_k]

    return await sync_to_async(_query_db)()
