"""OCR, classificação e extração de campos dos documentos."""

import re
import unicodedata
from datetime import date
from io import BytesIO

import pymupdf
import pytesseract
from PIL import Image
from sqlalchemy.orm import Session

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
_ISSUER_PATTERN = re.compile(
    r"\b(?:institui(?:ção|cao)(?: emissora)?|emitido por|emissor(?:a)?|cart[oó]rio)"
    r"\s*[:\-]\s*(.+)",
    re.IGNORECASE,
)
_ISSUER_KEYWORDS = (
    "universidade",
    "faculdade",
    "escola",
    "secretaria",
    "prefeitura",
    "cartorio",
)


def _normalizar(texto: str) -> str:
    decomposed = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def extrair_texto_ocr(content: bytes, content_type: str) -> str:
    """Executa OCR em imagem ou em páginas renderizadas de PDF."""
    images: list[Image.Image] = []
    if content_type == "application/pdf":
        with pymupdf.open(stream=content, filetype="pdf") as pdf_document:
            if len(pdf_document) > MAX_PDF_PAGES_FOR_OCR:
                raise ValueError("O PDF excede o limite de páginas para OCR.")
            for page in pdf_document:
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
                images.append(Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples))
    else:
        with Image.open(BytesIO(content)) as image:
            images.append(image.convert("RGB"))

    return "\n".join(pytesseract.image_to_string(image, lang=settings.ocr_language) for image in images)


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

    for line in texto.splitlines():
        clean_line = line.strip()
        if nome_extraido is None:
            name_match = _NAME_PATTERN.search(clean_line)
            if name_match:
                nome_extraido = name_match.group(1).strip(" \t:;,-")[:255] or None
        if emissor_extraido is None:
            issuer_match = _ISSUER_PATTERN.search(clean_line)
            if issuer_match:
                emissor_extraido = issuer_match.group(1).strip(" \t:;,-")[:255] or None
            elif any(keyword in _normalizar(clean_line) for keyword in _ISSUER_KEYWORDS):
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