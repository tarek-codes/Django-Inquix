import re
from app.config import settings


def chunk_text(text: str, metadata: dict | None = None) -> list[dict]:
    if metadata is None:
        metadata = {}

    paragraphs = re.split(r"\n\s*\n", text)
    target_chars = settings.chunk_size * 4

    chunks: list[dict] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) < target_chars:
            current += ("\n\n" if current else "") + para
        else:
            if current:
                chunks.append({
                    "content": current.strip(),
                    "token_count": len(current) // 4,
                    "metadata": {**metadata, "chunk_index": len(chunks)},
                })

            if len(para) > target_chars:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                sub = ""
                for sent in sentences:
                    if len(sub) + len(sent) < target_chars:
                        sub += (" " if sub else "") + sent
                    else:
                        if sub:
                            chunks.append({
                                "content": sub.strip(),
                                "token_count": len(sub) // 4,
                                "metadata": {**metadata, "chunk_index": len(chunks)},
                            })
                        sub = sent
                current = sub if sub else ""
            else:
                current = para

    if current.strip():
        chunks.append({
            "content": current.strip(),
            "token_count": len(current) // 4,
            "metadata": {**metadata, "chunk_index": len(chunks)},
        })

    return chunks
