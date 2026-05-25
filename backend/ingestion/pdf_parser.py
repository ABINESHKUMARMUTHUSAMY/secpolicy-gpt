import re
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional

FRAMEWORK_PATTERNS = {
    "NIST_800_53": {
        "name": "NIST SP 800-53",
        "keywords": ["800-53", "NIST SP 800", "security controls"],
        "control_id_pattern": r'\b([A-Z]{2}-\d+(?:\(\d+\))?(?:\.[a-z])?)\b',
        "section_pattern": r'^([A-Z]{2}-\d+(?:\(\d+\))?)\s+(.+)',
    },
    "NIST_CSF": {
        "name": "NIST CSF",
        "keywords": ["cybersecurity framework", "CSF", "identify", "protect", "detect", "respond", "recover"],
        "control_id_pattern": r'\b([A-Z]{2}\.[A-Z]{2}-\d+)\b',
        "section_pattern": r'^([A-Z]{2}\.[A-Z]{2}-\d+)\s+(.+)',
    },
    "ISO_27001": {
        "name": "ISO 27001",
        "keywords": ["ISO/IEC 27001", "ISO 27001", "Annex A", "ISMS"],
        "control_id_pattern": r'\b(A\.\d+(?:\.\d+){1,2})\b',
        "section_pattern": r'^(A\.\d+(?:\.\d+){1,2})\s+(.+)',
    },
    "SOC2": {
        "name": "SOC 2",
        "keywords": ["SOC 2", "trust service", "TSC", "AICPA", "CC1", "CC2", "CC3", "CC4", "CC5", "CC6"],
        "control_id_pattern": r'\b(CC\d+\.\d+|A\d+\.\d+|PI\d+\.\d+|C\d+\.\d+|P\d+\.\d+)\b',
        "section_pattern": r'^(CC\d+\.\d+)\s+(.+)',
    },
    "PCI_DSS": {
        "name": "PCI-DSS",
        "keywords": ["PCI DSS", "payment card", "cardholder data", "PCI Security Standards"],
        "control_id_pattern": r'\b(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?(?:\.\d{1,2})?)\b',
        "section_pattern": r'^Requirement (\d+(?:\.\d+)*)\s*:?\s*(.+)',
    },
    "CIS": {
        "name": "CIS Benchmarks",
        "keywords": ["CIS Controls", "CIS Benchmarks", "Center for Internet Security", "Safeguard"],
        "control_id_pattern": r'\b(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\b',
        "section_pattern": r'^(\d+\.\d+(?:\.\d+)?)\s+(.+)',
    },
}

FRAMEWORK_COLORS = {
    "NIST_800_53": "#3b82f6",
    "NIST_CSF": "#8b5cf6",
    "ISO_27001": "#10b981",
    "SOC2": "#f59e0b",
    "PCI_DSS": "#ef4444",
    "CIS": "#6366f1",
    "UNKNOWN": "#6b7280",
}


def detect_framework(filename: str, text_sample: str) -> str:
    name_lower = filename.lower()
    text_lower = text_sample[:3000].lower()

    scores = {}
    for fw_id, fw_info in FRAMEWORK_PATTERNS.items():
        score = 0
        for kw in fw_info["keywords"]:
            if kw.lower() in name_lower:
                score += 3
            if kw.lower() in text_lower:
                score += 1
        scores[fw_id] = score

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "UNKNOWN"


def extract_control_id(text: str, framework: str) -> Optional[str]:
    if framework not in FRAMEWORK_PATTERNS:
        return None
    pattern = FRAMEWORK_PATTERNS[framework]["control_id_pattern"]
    match = re.search(pattern, text[:200])
    return match.group(1) if match else None


def parse_pdf(file_path: str, framework: str = "auto") -> list[dict]:
    doc = fitz.open(file_path)
    filename = Path(file_path).name
    pages_text = []

    for page_num, page in enumerate(doc):
        text = page.get_text("text")
        if text.strip():
            pages_text.append({"page": page_num + 1, "text": text})

    doc.close()

    full_sample = " ".join(p["text"] for p in pages_text[:5])
    if framework == "auto":
        framework = detect_framework(filename, full_sample)

    return pages_text, framework
