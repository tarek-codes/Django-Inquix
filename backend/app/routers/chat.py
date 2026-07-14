import json
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.database import get_db, async_session
from app.models import KnowledgeBase, Document, Conversation, Message
from app.schemas import ChatRequest, ConversationResponse, MessageResponse
from app.services.retrieval import retrieve_chunks
from app.services.generation import generate_stream
from app.services.web_search import search_web

router = APIRouter()


@router.post("/kb/{kb_id}/chat")
async def chat(kb_id: str, req: ChatRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    conversation = None
    if req.conversation_id:
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == req.conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()

    if not conversation:
        conversation = Conversation(
            id=uuid.uuid4(), kb_id=kb_id,
            title=req.query[:100] if req.query else "New Chat",
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
        .limit(20)
    )
    history = history_result.scalars().all()
    chat_history = [{"role": m.role, "content": m.content} for m in history]

    user_msg = Message(
        conversation_id=conversation.id, role="user",
        content=req.query, cited_chunk_ids=[],
    )
    db.add(user_msg)
    await db.commit()

    doc_result = await db.execute(
        select(Document.filename).where(Document.kb_id == kb_id, Document.status == "ready")
    )
    kb_documents = [row[0] for row in doc_result.fetchall()]

    threshold = settings.similarity_threshold

    local_chunks = await retrieve_chunks(req.query, kb_id)

    has_relevant_docs = any(
        c.get("similarity", 0) >= threshold for c in local_chunks
    )

    if has_relevant_docs:
        web_chunks = []
    else:
        web_chunks = await search_web(req.query, max_results=2)

    chunks = list(local_chunks)
    if web_chunks:
        offset = len(chunks)
        for i, wc in enumerate(web_chunks):
            wc["chunk_index"] = offset + i
            chunks.append(wc)

    cited_chunk_ids = [
        c["id"] for c in chunks
        if c.get("similarity", 1) >= threshold and c.get("id")
    ]

    conv_id = str(conversation.id)

    async def stream_response():
        full_answer = ""
        try:
            async for token in generate_stream(req.query, chunks, chat_history, kb_documents, images=req.images):
                full_answer += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            async with async_session() as save_session:
                assistant_msg = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_answer,
                    cited_chunk_ids=cited_chunk_ids,
                )
                save_session.add(assistant_msg)
                await save_session.commit()

            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conv_id, 'citations': chunks})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/kb/{kb_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(kb_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.kb_id == kb_id)
        .order_by(Conversation.created_at.desc())
    )
    return result.scalars().all()


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageResponse])
async def get_messages(conv_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()
