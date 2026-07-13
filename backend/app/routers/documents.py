import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import KnowledgeBase, Document, Chunk
from app.schemas import DocumentResponse
from app.config import settings
from app.services.extraction import extract_text, compute_content_hash, save_upload, detect_source_type
from app.services.chunking import chunk_text
from app.services.embedding import get_embedding

router = APIRouter()


@router.post("/kb/{kb_id}/documents", response_model=DocumentResponse)
async def upload_document(kb_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    file_bytes = await file.read()
    filename = file.filename or "untitled"
    source_type = detect_source_type(file.content_type or "text/plain")

    file_path, safe_filename = await save_upload(kb_id, file_bytes, filename)

    doc = Document(
        kb_id=kb_id,
        source_type=source_type,
        filename=filename,
        storage_path=file_path,
        title=filename,
        status="processing",
        file_size=len(file_bytes),
        mime_type=file.content_type,
        metadata_={"safe_filename": safe_filename},
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    try:
        extracted_text, extraction_metadata = await extract_text(file_path, source_type, filename)

        if not extracted_text.strip():
            doc.status = "ready"
            doc.content_hash = compute_content_hash("")
            await db.commit()
            await db.refresh(doc)
            return doc

        doc.content_hash = compute_content_hash(extracted_text)

        chunks_data = chunk_text(extracted_text, extraction_metadata)

        for i, chunk_data in enumerate(chunks_data):
            embedding = await get_embedding(chunk_data["content"])
            chunk = Chunk(
                document_id=doc.id,
                kb_id=kb_id,
                chunk_index=i,
                content=chunk_data["content"],
                embedding=embedding,
                token_count=chunk_data["token_count"],
                chunk_metadata=chunk_data["metadata"],
                status="active",
                content_hash=compute_content_hash(chunk_data["content"]),
            )
            db.add(chunk)

        doc.status = "ready"
        await db.commit()
        await db.refresh(doc)

    except Exception as e:
        doc.status = "failed"
        doc.metadata_ = {**doc.metadata_, "error": str(e)}
        await db.commit()
        await db.refresh(doc)

    return doc


@router.get("/kb/{kb_id}/documents", response_model=list[DocumentResponse])
async def list_documents(kb_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Document)
        .where(Document.kb_id == kb_id)
        .order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/kb/{kb_id}/documents/{doc_id}")
async def delete_document(kb_id: str, doc_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.kb_id == kb_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.storage_path and os.path.exists(doc.storage_path):
        os.remove(doc.storage_path)

    await db.delete(doc)
    await db.commit()
    return {"status": "deleted"}
