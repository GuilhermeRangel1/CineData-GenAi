"""Stage the Gold database on Docker's local filesystem before serving queries."""

import hashlib
import os
import re
import shutil
import tempfile
from pathlib import Path


def _digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def prepare_gold_cache() -> None:
    """Copy a verified Gold snapshot atomically into the persistent Docker volume."""

    source = Path(os.environ["GENAI_GOLD_SOURCE_PATH"])
    manifest = Path(os.environ["GENAI_GOLD_FINGERPRINT_PATH"])
    target = Path(os.environ["GENAI_GOLD_DATABASE_PATH"])

    parts = manifest.read_text(encoding="ascii").split()
    if len(parts) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
        raise ValueError(f"Manifesto SHA-256 inválido: {manifest}")
    expected_digest, expected_size = parts[0].lower(), int(parts[1])
    source_digest, source_size = _digest(source)
    if (source_digest, source_size) != (expected_digest, expected_size):
        raise ValueError(f"Gold de origem não corresponde ao manifesto: {source}")

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size == expected_size:
        if _digest(target)[0] == expected_digest:
            print(f"Gold local já atualizado: {target}", flush=True)
            return

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            with source.open("rb") as source_file:
                shutil.copyfileobj(source_file, temporary, length=1024 * 1024)
        if _digest(temporary_path) != (expected_digest, expected_size):
            raise ValueError("A cópia local do Gold falhou na verificação SHA-256.")
        temporary_path.replace(target)
        print(f"Gold copiado para o volume local do Docker: {target}", flush=True)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    prepare_gold_cache()
