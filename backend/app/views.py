import os
import json
import uuid
import aiofiles
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import sync_to_async

from django.core.exceptions import ValidationError
from app.models import KnowledgeBase, Document, Chunk, Conversation, Message
from app.config import settings
from app.services.extraction import extract_text, compute_content_hash, save_upload, detect_source_type, extract_from_audio
from app.services.chunking import chunk_text
from app.services.embedding import get_embedding
from app.services.retrieval import retrieve_chunks
from app.services.generation import generate_stream
from app.services.web_search import search_web
from app.services.tts import text_to_speech


# Serializer helpers
def serialize_kb(kb, doc_count=0):
    return {
        "id": str(kb.id),
        "name": kb.name,
        "description": kb.description,
        "created_at": kb.created_at.isoformat() if kb.created_at else None,
        "document_count": doc_count
    }


def serialize_doc(doc):
    return {
        "id": str(doc.id),
        "kb_id": str(doc.kb_id),
        "source_type": doc.source_type,
        "filename": doc.filename,
        "title": doc.title,
        "status": doc.status,
        "version": doc.version,
        "file_size": doc.file_size,
        "mime_type": doc.mime_type,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


def serialize_conv(conv):
    return {
        "id": str(conv.id),
        "kb_id": str(conv.kb_id),
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }


def serialize_msg(msg):
    return {
        "id": str(msg.id),
        "role": msg.role,
        "content": msg.content,
        "cited_chunk_ids": msg.cited_chunk_ids or [],
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


# Health check
async def health_check(request):
    return JsonResponse({"status": "ok"})


# Root API welcome
async def root(request):
    return JsonResponse({"name": "Inquix API", "version": "0.1.0"})


# KB views
@csrf_exempt
async def list_or_create_kb(request):
    if request.method == 'GET':
        def _get_kbs():
            kbs = list(KnowledgeBase.objects.order_by('-created_at'))
            responses = []
            for kb in kbs:
                doc_count = Document.objects.filter(kb=kb).count()
                responses.append(serialize_kb(kb, doc_count))
            return responses

        data = await sync_to_async(_get_kbs)()
        return JsonResponse(data, safe=False)

    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
            name = body.get('name')
            description = body.get('description', '')
        except Exception:
            return JsonResponse({"detail": "Invalid payload"}, status=400)

        if not name:
            return JsonResponse({"detail": "Name is required"}, status=400)

        kb = await sync_to_async(KnowledgeBase.objects.create)(name=name, description=description)
        return JsonResponse(serialize_kb(kb, 0))

    return HttpResponse("Method not allowed", status=405)


@csrf_exempt
async def get_or_delete_kb(request, kb_id):
    try:
        kb = await sync_to_async(KnowledgeBase.objects.get)(id=kb_id)
    except KnowledgeBase.DoesNotExist:
        return JsonResponse({"detail": "Knowledge base not found"}, status=404)

    if request.method == 'GET':
        doc_count = await sync_to_async(Document.objects.filter(kb=kb).count)()
        return JsonResponse(serialize_kb(kb, doc_count))

    elif request.method == 'DELETE':
        await sync_to_async(kb.delete)()
        return JsonResponse({"status": "deleted"})

    return HttpResponse("Method not allowed", status=405)


# Document views
@csrf_exempt
async def list_or_create_doc(request, kb_id):
    try:
        kb = await sync_to_async(KnowledgeBase.objects.get)(id=kb_id)
    except KnowledgeBase.DoesNotExist:
        return JsonResponse({"detail": "Knowledge base not found"}, status=404)

    if request.method == 'GET':
        def _get_docs():
            docs = list(Document.objects.filter(kb=kb).order_by('-created_at'))
            return [serialize_doc(d) for d in docs]
        data = await sync_to_async(_get_docs)()
        return JsonResponse(data, safe=False)

    elif request.method == 'POST':
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({"detail": "No file uploaded"}, status=400)

        file_bytes = file.read()
        filename = file.name or "untitled"
        source_type = detect_source_type(file.content_type or "text/plain")

        file_path, safe_filename = await save_upload(kb_id, file_bytes, filename)

        doc = await sync_to_async(Document.objects.create)(
            kb=kb,
            source_type=source_type,
            filename=filename,
            storage_path=file_path,
            title=filename,
            status="processing",
            file_size=len(file_bytes),
            mime_type=file.content_type,
            metadata={"safe_filename": safe_filename},
        )

        try:
            extracted_text, extraction_metadata = await extract_text(file_path, source_type, filename)

            if not extracted_text.strip():
                doc.status = "ready"
                doc.content_hash = compute_content_hash("")
                await sync_to_async(doc.save)()
                return JsonResponse(serialize_doc(doc))

            doc.content_hash = compute_content_hash(extracted_text)

            chunks_data = chunk_text(extracted_text, extraction_metadata)

            chunks_to_create = []
            for i, chunk_data in enumerate(chunks_data):
                embedding = await get_embedding(chunk_data["content"])
                chunk = Chunk(
                    document=doc,
                    kb=kb,
                    chunk_index=i,
                    content=chunk_data["content"],
                    embedding=embedding,
                    token_count=chunk_data["token_count"],
                    chunk_metadata=chunk_data["metadata"],
                    status="active",
                    content_hash=compute_content_hash(chunk_data["content"]),
                )
                chunks_to_create.append(chunk)

            def _bulk_create(chunks):
                Chunk.objects.bulk_create(chunks)

            await sync_to_async(_bulk_create)(chunks_to_create)

            doc.status = "ready"
            await sync_to_async(doc.save)()

        except Exception as e:
            doc.status = "failed"
            doc.metadata = {**doc.metadata, "error": str(e)}
            await sync_to_async(doc.save)()

        return JsonResponse(serialize_doc(doc))

    return HttpResponse("Method not allowed", status=405)


@csrf_exempt
async def delete_doc(request, kb_id, doc_id):
    if request.method != 'DELETE':
        return HttpResponse("Method not allowed", status=405)

    try:
        doc = await sync_to_async(Document.objects.get)(id=doc_id, kb_id=kb_id)
    except Document.DoesNotExist:
        return JsonResponse({"detail": "Document not found"}, status=404)

    if doc.storage_path and os.path.exists(doc.storage_path):
        try:
            os.remove(doc.storage_path)
        except Exception:
            pass

    await sync_to_async(doc.delete)()
    return JsonResponse({"status": "deleted"})


# Chat view
@csrf_exempt
async def chat_view(request, kb_id):
    if request.method != 'POST':
        return HttpResponse("Method not allowed", status=405)

    try:
        kb = await sync_to_async(KnowledgeBase.objects.get)(id=kb_id)
    except KnowledgeBase.DoesNotExist:
        return JsonResponse({"detail": "Knowledge base not found"}, status=404)

    try:
        body = json.loads(request.body)
        query = body.get('query')
        conversation_id = body.get('conversation_id')
        images = body.get('images', [])
    except Exception:
        return JsonResponse({"detail": "Invalid request payload"}, status=400)

    if not query:
        return JsonResponse({"detail": "Query is required"}, status=400)

    conversation = None
    if conversation_id:
        try:
            conversation = await sync_to_async(Conversation.objects.get)(id=conversation_id)
        except (Conversation.DoesNotExist, ValidationError, ValueError):
            pass

    if not conversation:
        conversation = await sync_to_async(Conversation.objects.create)(
            kb=kb,
            title=query[:100] if query else "New Chat"
        )

    user_msg = Message(
        conversation=conversation,
        role="user",
        content=query,
        cited_chunk_ids=[],
    )
    await sync_to_async(user_msg.save)()

    conv_id_str = str(conversation.id)

    async def stream_response():
        full_answer = ""
        try:
            # Perform history, document, vector search, and web queries inside the generator
            # to prevent blocking the initial EventSource connection startup.
            def _get_history(conv_id):
                history = list(Message.objects.filter(conversation_id=conv_id).order_by('created_at')[:20])
                return [{"role": m.role, "content": m.content} for m in history]

            chat_history = await sync_to_async(_get_history)(conversation.id)

            def _get_kb_documents():
                return list(Document.objects.filter(kb=kb, status="ready").values_list('filename', flat=True))

            kb_documents = await sync_to_async(_get_kb_documents)()

            threshold = settings.similarity_threshold
            local_chunks = await retrieve_chunks(query, kb_id)
            
            # Keep only chunks that actually meet the similarity threshold
            relevant_local_chunks = [c for c in local_chunks if c.get("similarity", 0) >= threshold]

            if relevant_local_chunks:
                web_chunks = []
            else:
                web_chunks = await search_web(query, max_results=2)

            chunks = list(relevant_local_chunks)
            if web_chunks:
                offset = len(chunks)
                for i, wc in enumerate(web_chunks):
                    wc["chunk_index"] = offset + i
                    chunks.append(wc)

            async for token in generate_stream(query, chunks, chat_history, kb_documents, images=images):
                full_answer += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            assistant_msg = Message(
                conversation=conversation,
                role="assistant",
                content=full_answer,
                cited_chunk_ids=[],
            )
            await sync_to_async(assistant_msg.save)()

            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conv_id_str, 'citations': []})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    response = StreamingHttpResponse(
        stream_response(),
        content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["Connection"] = "keep-alive"
    response["X-Accel-Buffering"] = "no"
    return response


# Conversation views
@csrf_exempt
async def list_conversations(request, kb_id):
    if request.method != 'GET':
        return HttpResponse("Method not allowed", status=405)

    try:
        kb = await sync_to_async(KnowledgeBase.objects.get)(id=kb_id)
    except KnowledgeBase.DoesNotExist:
        return JsonResponse({"detail": "Knowledge base not found"}, status=404)

    def _get_conversations():
        convs = list(Conversation.objects.filter(kb=kb).order_by('-created_at'))
        return [serialize_conv(c) for c in convs]

    data = await sync_to_async(_get_conversations)()
    return JsonResponse(data, safe=False)


@csrf_exempt
async def get_messages(request, conv_id):
    if request.method != 'GET':
        return HttpResponse("Method not allowed", status=405)

    try:
        conversation = await sync_to_async(Conversation.objects.get)(id=conv_id)
    except Conversation.DoesNotExist:
        return JsonResponse({"detail": "Conversation not found"}, status=404)

    def _get_messages():
        msgs = list(Message.objects.filter(conversation=conversation).order_by('created_at'))
        return [serialize_msg(m) for m in msgs]

    data = await sync_to_async(_get_messages)()
    return JsonResponse(data, safe=False)


# Audio view
@csrf_exempt
async def transcribe_audio(request):
    if request.method != 'POST':
        return HttpResponse("Method not allowed", status=405)

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({"detail": "No audio file uploaded"}, status=400)

    content_type = file.content_type or ""
    if not (content_type.startswith("audio/") or content_type == "application/octet-stream"):
        return JsonResponse({"detail": f"Audio file required, got: {content_type}"}, status=400)

    filename = file.name or "recording.webm"
    ext = os.path.splitext(filename)[1] or ".webm"
    file_id = str(uuid.uuid4())
    tmp_dir = os.path.join(settings.upload_dir, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    file_path = os.path.join(tmp_dir, f"{file_id}{ext}")

    file_bytes = file.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_bytes)

    try:
        text, metadata = await extract_from_audio(file_path)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    return JsonResponse({"text": text, "language": metadata.get("language", "en")})


# TTS view
@csrf_exempt
async def synthesize_speech(request):
    if request.method != 'POST':
        return HttpResponse("Method not allowed", status=405)

    try:
        body = json.loads(request.body)
        text = body.get('text', '')
    except Exception:
        return JsonResponse({"detail": "Invalid request payload"}, status=400)

    if not text.strip():
        return JsonResponse({"detail": "Text is required"}, status=400)

    audio = await text_to_speech(text)
    if not audio:
        return JsonResponse({"detail": "TTS generation failed"}, status=500)

    content_type = "audio/wav" if audio.startswith(b"RIFF") else "audio/mpeg"
    return HttpResponse(audio, content_type=content_type)
