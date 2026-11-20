"""Abstração de armazenamento e implementação local."""

import re
from pathlib import Path
from typing import Protocol


class StorageService(Protocol):
    """Interface substituível para armazenamento de arquivos."""

    def save(self, key: str, content: bytes) -> None:
        """Armazena o conteúdo associado à chave."""

    def read(self, key: str) -> bytes:
        """Lê o conteúdo associado à chave."""

    def delete(self, key: str) -> None:
        """Remove o conteúdo associado à chave."""


class LocalStorageService:
    """Armazena documentos em um diretório local não público."""

    _KEY_PATTERN = re.compile(r"^[a-f0-9]{32}\.(?:pdf|jpg|png)$")

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path_for(self, key: str) -> Path:
        if not self._KEY_PATTERN.fullmatch(key):
            raise ValueError("Chave de armazenamento inválida.")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Chave fora do diretório de armazenamento.")
        return path

    def save(self, key: str, content: bytes) -> None:
        """Armazena o conteúdo associado à chave."""
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read(self, key: str) -> bytes:
        """Lê o conteúdo associado à chave."""
        return self._path_for(key).read_bytes()

    def delete(self, key: str) -> None:
        """Remove o conteúdo associado à chave, se existir."""
        self._path_for(key).unlink(missing_ok=True)