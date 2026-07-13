from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel


class KBCreate(BaseModel):
    name: str
    description: str = ""


class KBResponse(BaseModel):
    id: UUID
    name: str
    description: str
    created_at: datetime
    document_count: int = 0

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: UUID
    kb_id: UUID
    source_type: str
    filename: str
    title: Optional[str] = None
    status: str
    version: int
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[UUID] = None


class ConversationResponse(BaseModel):
    id: UUID
    kb_id: UUID
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    cited_chunk_ids: list = []
    created_at: datetime

    model_config = {"from_attributes": True}
