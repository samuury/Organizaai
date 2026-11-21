"""OCR, classificação e extração de campos dos documentos."""

import base64
import re
import shutil
import unicodedata
from datetime import date
from io import BytesIO

import httpx
import pymupdf
import pytesseract
from PIL import Image

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.audit.service import registrar_auditoria
from app.modules.wallet.models import WalletDocument
from app.modules.wallet.storage import LocalStorageService

MAX_PDF_PAGES_FOR_OCR = 25

_KEYWORDS = {
    "diploma": (
        "diploma",
        "graduacao",
        "certificado de conclusao",
        "conclusao de curso",
        "grau academico",
        "curso superior",
    ),
    "certidao": (
        "certidao",
        "registro civil",
        "nascimento",
        "casamento",
        "obito",
        "cartorio",
    ),
    "comprovante": (
        "comprovante",
        "declaracao",
        "matricula",
        "conta de agua",
        "conta de energia",
        "residencia",
        "endereco",
        "pagamento",
        "renda",
    ),
}
_DATE_PATTERNS = (
    re.compile(r"\b(?P<day>\d{1,2})[/.\-](?P<month>\d{1,2})[/.\-](?P<year>\d{4})\b"),
    re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b"),
)
_NAME_PATTERN = re.compile(
    r"\b(?:nome(?: completo)?(?: do(?:a)? (?:aluno|titular|formando))?|"
    r"titular|aluno(?:a)?|outorgado(?:a)?)\s*[:\-]\s*(.+)",
    re.IGNORECASE,
)
_NAME_PROSE_PATTERN = re.compile(
    r"\bque\s+([A-ZÀ-Ú][a-zA-Zà-úÀ-Ú]+(?:\s+[A-ZÀ-Ú][a-zA-Zà-úÀ-Ú]+)+)\s*,\s*(?:matr[ií]cula|cpf|portador|nascid)",
    re.IGNORECASE,
)
_ISSUER_PATTERN = re.compile(
    r"\b(?:institui(?:ção|cao)(?: emissora)?|emitido por|emissor(?:a)?|cart[oó]rio)"
    r"\s*[:\-]\s*(.+)",
    re.IGNORECASE,
)
_ISSUER_KEYWORDS = (
    "instituto",
    "universidade",
    "faculdade",
    "colegio",
    "escola",
    "secretaria",
    "prefeitura",
    "cartorio",
)


def _normalizar(texto: str) -> str:
    decomposed = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _extrair_texto_com_claude(content: bytes, content_type: str) -> str | None:
    """Extrai texto do arquivo via Claude Vision quando o Tesseract local não estiver disponível."""
    if not settings.anthropic_api_key:
        return None
    try:
        if content_type == "application/pdf":
            media_type = "application/pdf"
            source_type = "document"
        elif content_type in ("image/png", "image/jpeg", "image/jpg", "image/webp"):
            media_type = "image/jpeg" if content_type == "image/jpg" else content_type
            source_type = "image"
        else:
            return None

        b64_data = base64.b64encode(content).decode("utf-8")
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        content_block = {
            "type": source_type,
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64_data,
            },
        }
        modelo = settings.anthropic_model or "claude-haiku-5-5"
        if modelo == "claude-5-5-haiku":
            modelo = "claude-haiku-5-5"
        payload = {
            "model": modelo,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        content_block,
                        {
                            "type": "text",
                            "text": "Transcreva todo o texto contido neste documento fielmente, sem comentários adicionais.",
                        },
                    ],
                }
            ],
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text_blocks = [
                    block.get("text", "")
                    for block in data.get("content", [])
                    if block.get("type") == "text"
                ]
                return "\n".join(text_blocks).strip()
    except Exception:
        return None
    return None


def extrair_texto_ocr(content: bytes, content_type: str) -> str:
    """Extrai texto diretamente do PDF digital ou executa OCR via Tesseract / Claude Vision."""
    # 1. Se for PDF, tenta extrair o texto digital embutido primeiro
    if content_type == "application/pdf":
        with pymupdf.open(stream=content, filetype="pdf") as pdf_document:
            if len(pdf_document) > MAX_PDF_PAGES_FOR_OCR:
                raise ValueError("O PDF excede o limite de páginas para OCR.")
            textos_paginas = [page.get_text() for page in pdf_document]
            texto_direto = "\n".join(t.strip() for t in textos_paginas if t.strip())
            if len(texto_direto) >= 15:
                return texto_direto

    # 2. Se for imagem ou PDF escaneado (sem texto digital)
    if shutil.which("tesseract"):
        images: list[Image.Image] = []
        if content_type == "application/pdf":
            with pymupdf.open(stream=content, filetype="pdf") as pdf_document:
                for page in pdf_document:
                    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
                    images.append(Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples))
        else:
            with Image.open(BytesIO(content)) as image:
                images.append(image.convert("RGB"))

        return "\n".join(pytesseract.image_to_string(image, lang=settings.ocr_language) for image in images)

    # 3. Fallback inteligente com Claude Vision quando Tesseract não está no host
    texto_ia = _extrair_texto_com_claude(content, content_type)
    if texto_ia:
        return texto_ia

    raise RuntimeError(
        "Tesseract OCR não encontrado no servidor. Instale com: sudo apt install -y tesseract-ocr tesseract-ocr-por"
    )


def classificar_tipo(texto: str) -> str | None:
    """Classifica o documento pela categoria com mais palavras-chave."""
    normalized_text = _normalizar(texto)
    scores = {
        category: sum(normalized_text.count(keyword) for keyword in keywords)
        for category, keywords in _KEYWORDS.items()
    }
    highest_score = max(scores.values(), default=0)
    winners = [category for category, score in scores.items() if score == highest_score and score > 0]
    return winners[0] if len(winners) == 1 else None


def extrair_campos(texto: str) -> dict[str, str | date | None]:
    """Extrai nome, data e emissor por rótulos e padrões textuais."""
    nome_extraido = None
    emissor_extraido = None

    # Tenta extrair nome do titular
    for line in texto.splitlines():
        clean_line = line.strip()
        if nome_extraido is None:
            name_match = _NAME_PATTERN.search(clean_line)
            if name_match:
                nome_extraido = name_match.group(1).strip(" \t:;,-")[:255] or None

    if nome_extraido is None:
        prose_match = _NAME_PROSE_PATTERN.search(texto)
        if prose_match:
            nome_extraido = prose_match.group(1).strip(" \t:;,-")[:255] or None

    # Tenta extrair instituição emissora
    for line in texto.splitlines():
        clean_line = line.strip()
        if emissor_extraido is None:
            issuer_match = _ISSUER_PATTERN.search(clean_line)
            if issuer_match and not clean_line.lower().startswith("código"):
                emissor_extraido = issuer_match.group(1).strip(" \t:;,-")[:255] or None
            elif any(keyword in _normalizar(clean_line) for keyword in _ISSUER_KEYWORDS) and not clean_line.lower().startswith("código"):
                emissor_extraido = clean_line[:255] or None

    data_extraida = None
    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(texto):
            try:
                data_extraida = date(
                    int(match.group("year")),
                    int(match.group("month")),
                    int(match.group("day")),
                )
                break
            except ValueError:
                continue
        if data_extraida is not None:
            break

    return {
        "nome_extraido": nome_extraido,
        "data_extraida": data_extraida,
        "emissor_extraido": emissor_extraido,
    }


def processar_documento(document_id: int) -> None:
    """Executa OCR e persiste os campos extraídos em uma sessão independente."""
    with SessionLocal() as session:
        document = session.get(WalletDocument, document_id)
        if document is None:
            return

        document.estado_processamento = "processando"
        session.commit()

        try:
            content = LocalStorageService(settings.storage_path).read(document.storage_key)
            text = extrair_texto_ocr(content, document.content_type)
            fields = extrair_campos(text)
            document.texto_ocr = text
            document.tipo_documento = classificar_tipo(text)
            document.nome_extraido = fields["nome_extraido"]
            document.data_extraida = fields["data_extraida"]
            document.emissor_extraido = fields["emissor_extraido"]
            document.estado_processamento = "concluido"
            document.erro_processamento = None
            action = "wallet.ocr_concluido"
        except Exception:
            session.rollback()
            document = session.get(WalletDocument, document_id)
            if document is None:
                return
            document.estado_processamento = "falhou"
            document.erro_processamento = "Não foi possível processar o documento."
            action = "wallet.ocr_falhou"

        registrar_auditoria(
            session,
            usuario_id=document.usuario_id,
            acao=action,
            entidade="wallet_documents",
            entidade_id=document.id,
        )
        session.commit()
        if action == "wallet.ocr_falhou":
            from app.core.notifications import notificar_falha_ocr_em_massa

            notificar_falha_ocr_em_massa()