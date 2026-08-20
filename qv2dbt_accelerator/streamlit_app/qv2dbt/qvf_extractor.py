"""Extract the load script from a binary Qlik app file (.qvf / .qvw).

QlikView (.qvw) and Qlik Sense (.qvf) apps are binary containers, not plain
text. The load script is stored inside, usually zlib-compressed. This module
locates the script, reconstructs clean text, and — because Qlik frequently
stores more than one copy of the script (a current copy plus a backup/lineage
copy that may point at different data connections) — keeps only the canonical
tab-structured copy so the downstream parser sees each table once.

Public API:
    is_binary_qlik(path)  -> bool
    extract_script(path)  -> str   (raises ExtractionError on failure)
"""
from __future__ import annotations

import re
import zlib

TAB_MARKER = "///$tab"
_SCRIPT_TOKENS = (b"LOAD", b"RESIDENT", b"FROM ", b"SQL SELECT", b"///$tab")


class ExtractionError(RuntimeError):
    pass


def is_binary_qlik(path: str) -> bool:
    """True if the file is a binary Qlik app rather than a text .qvs."""
    low = path.lower()
    if low.endswith(".qvs"):
        return False
    if low.endswith((".qvf", ".qvw")):
        return True
    # Fall back to sniffing: a text script decodes as UTF-8 and has LOAD/FROM.
    with open(path, "rb") as fh:
        head = fh.read(4096)
    if b"\x00" in head:
        return True
    try:
        head.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def _decompress_streams(data: bytes) -> list[bytes]:
    """Return every decompressible zlib stream that looks script-like,
    best (most script tokens) first."""
    results: list[tuple[int, bytes]] = []
    for m in re.finditer(b"\x78\x9c", data):  # zlib default-compression header
        off = m.start()
        try:
            d = zlib.decompressobj().decompress(data[off:])
        except zlib.error:
            continue
        if not d:
            continue
        up = d.upper()
        score = sum(up.count(t.upper()) for t in _SCRIPT_TOKENS)
        if score:
            results.append((score, d))
    results.sort(key=lambda t: t[0], reverse=True)
    return [d for _, d in results]


def _clean_text(raw: str) -> str:
    """Strip binary noise, keep printable ASCII + tabs/newlines."""
    m = re.search(r"\x00{4,}", raw)
    if m:
        raw = raw[: m.start()]
    return "".join(
        ch if (ch in "\n\t" or 32 <= ord(ch) < 127) else "" for ch in raw
    )


def _canonical_copy(script: str) -> str:
    """Keep only the first complete copy of the script.

    Qlik often stores the script twice back-to-back. We cut at the point where
    the first declared table name reappears (start of the duplicate copy).
    """
    # Find the first table declaration:  [Name]:  or  Name:  followed by LOAD.
    decl = re.search(
        r"(?m)^\s*\[?([A-Za-z_][\w \-]*?)\]?\s*:\s*(?:\n\s*)?(?:noconcatenate\s+)?LOAD",
        script, re.IGNORECASE)
    if not decl:
        return script
    name = decl.group(1).strip()
    # Occurrences of that exact declaration ("Name:" / "[Name]:").
    occ = [m.start() for m in re.finditer(
        r"(?m)^\s*\[?" + re.escape(name) + r"\]?\s*:", script)]
    if len(occ) > 1:
        return script[: occ[1]].rstrip()
    return script.rstrip()


def extract_script(path: str) -> str:
    """Extract a clean, single-copy load script from a .qvf/.qvw file."""
    with open(path, "rb") as fh:
        data = fh.read()

    for stream in _decompress_streams(data):
        text = stream.decode("latin-1", errors="replace")
        idx = text.find(TAB_MARKER)
        if idx == -1:
            # No tab markers: fall back to the first LOAD/SET we can find.
            m = re.search(r"(?is)\b(SET|LET)\b|\bLOAD\b", text)
            if m is None:
                continue
            idx = max(0, m.start() - 60)
        cleaned = _clean_text(text[idx:])
        if TAB_MARKER in cleaned or re.search(r"(?is)\bload\b.*\bfrom\b", cleaned):
            return _canonical_copy(cleaned) + "\n"

    raise ExtractionError(
        f"Could not locate a load script inside '{path}'. The file may be "
        f"encrypted, section-access protected, or an unsupported Qlik version. "
        f"Export the script from Qlik (Script Editor > ... > Export Script) and "
        f"run the accelerator on the resulting .qvs.")
