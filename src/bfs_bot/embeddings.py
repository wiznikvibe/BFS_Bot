from __future__ import annotations

import hashlib
import math
import re


TOKEN_RE = re.compile(r"[a-z0-9]{3,}", re.I)


def hash_embedding(text: str, dimensions: int = 384) -> list[float]:
    vector = [0.0] * dimensions
    for token in TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def normalize_embedding(value: object) -> list[float]:
    """Accept list/tuple/str embeddings from JSON or vector drivers."""
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            stripped = stripped[1:-1]
        if not stripped:
            return []
        return [float(part) for part in stripped.split(",")]
    if isinstance(value, (list, tuple)):
        return [float(part) for part in value]
    if hasattr(value, "tolist"):
        return [float(part) for part in value.tolist()]
    return [float(part) for part in list(value)]  # type: ignore[arg-type]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))

