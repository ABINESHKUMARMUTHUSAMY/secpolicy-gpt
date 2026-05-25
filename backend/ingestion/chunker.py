import re
from typing import Optional
from .pdf_parser import FRAMEWORK_PATTERNS, extract_control_id


CHUNK_SIZE = 600
CHUNK_OVERLAP = 80


def _split_into_sentences(text: str) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def _build_chunks_from_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) > 50:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def chunk_pages(pages: list[dict], framework: str, filename: str) -> list[dict]:
    chunks = []
    chunk_id = 0

    # Try to chunk at control boundaries first
    pattern_info = FRAMEWORK_PATTERNS.get(framework, {})
    section_pattern = pattern_info.get("section_pattern")
    control_id_pattern = pattern_info.get("control_id_pattern")

    for page_data in pages:
        page_num = page_data["page"]
        text = page_data["text"]

        # Split on control ID boundaries if we know the framework
        if section_pattern:
            lines = text.split("\n")
            current_section_id = None
            current_section_name = None
            current_buffer = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                section_match = re.match(section_pattern, line)
                if section_match:
                    # Flush previous section
                    if current_buffer:
                        section_text = "\n".join(current_buffer)
                        for sub_chunk in _build_chunks_from_text(section_text, CHUNK_SIZE, CHUNK_OVERLAP):
                            chunks.append({
                                "id": f"{framework}_{chunk_id}",
                                "text": sub_chunk,
                                "framework": framework,
                                "control_id": current_section_id,
                                "control_name": current_section_name,
                                "page": page_num,
                                "source_file": filename,
                            })
                            chunk_id += 1
                    current_section_id = section_match.group(1)
                    current_section_name = section_match.group(2).strip() if len(section_match.groups()) > 1 else None
                    current_buffer = [line]
                else:
                    current_buffer.append(line)

            # Flush last section
            if current_buffer:
                section_text = "\n".join(current_buffer)
                ctrl_id = current_section_id or extract_control_id(section_text, framework)
                for sub_chunk in _build_chunks_from_text(section_text, CHUNK_SIZE, CHUNK_OVERLAP):
                    chunks.append({
                        "id": f"{framework}_{chunk_id}",
                        "text": sub_chunk,
                        "framework": framework,
                        "control_id": ctrl_id,
                        "control_name": current_section_name,
                        "page": page_num,
                        "source_file": filename,
                    })
                    chunk_id += 1
        else:
            # Generic chunking for unknown frameworks
            for sub_chunk in _build_chunks_from_text(text, CHUNK_SIZE, CHUNK_OVERLAP):
                ctrl_id = extract_control_id(sub_chunk, framework)
                chunks.append({
                    "id": f"{framework}_{chunk_id}",
                    "text": sub_chunk,
                    "framework": framework,
                    "control_id": ctrl_id,
                    "control_name": None,
                    "page": page_num,
                    "source_file": filename,
                })
                chunk_id += 1

    return [c for c in chunks if len(c["text"].strip()) > 30]
