import uuid
# pyrefly: ignore [missing-import]
from django.db import models
# pyrefly: ignore [missing-import]
from pgvector.django import VectorField

class KnowledgeBase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "knowledge_bases"


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kb = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name="documents",
        db_column="kb_id"
    )
    source_type = models.CharField(max_length=50)
    filename = models.CharField(max_length=500)
    storage_path = models.TextField(null=True, blank=True)
    title = models.CharField(max_length=500, null=True, blank=True)
    status = models.CharField(max_length=50, default="uploading")
    version = models.IntegerField(default=1)
    content_hash = models.CharField(max_length=64, null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=255, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True, db_column="metadata")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "documents"


class Chunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks",
        db_column="document_id"
    )
    kb = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name="chunks",
        db_column="kb_id"
    )
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding = VectorField(dimensions=768, null=True, blank=True)
    token_count = models.IntegerField(null=True, blank=True)
    chunk_metadata = models.JSONField(default=dict, blank=True, db_column="metadata")
    status = models.CharField(max_length=50, default="active")
    content_hash = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chunks"


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kb = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name="conversations",
        db_column="kb_id"
    )
    title = models.CharField(max_length=500, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversations"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        db_column="conversation_id"
    )
    role = models.CharField(max_length=50)
    content = models.TextField()
    cited_chunk_ids = models.JSONField(default=list, blank=True)
    token_usage = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
