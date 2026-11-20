"""Serviço do assistente inteligente Organiza AI utilizando Anthropic Claude Haiku."""

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.modules.chat.schemas import MensagemChat

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é o Assistente Virtual Oficial do Organiza AI, uma carteira digital inteligente e segura para guarda, emissão e verificação de documentos e certificados sob as diretrizes da LGPD (Lei Geral de Proteção de Dados).

Os três perfis do sistema são:
1. CIDADÃO (Titular):
   - Armazena documentos próprios (diplomas, certidões, comprovantes).
   - Extrai automaticamente dados via OCR em português.
   - Concede acesso temporário com data de validade para empresas parceiras.
   - Pode revogar qualquer concessão de acesso a qualquer momento.
2. INSTITUIÇÃO (Emissora):
   - Emite diplomas, certidões e comprovantes autenticados com hash SHA-256 e QR Code público.
   - Realiza emissão individual ou em lote via arquivos CSV e JSON.
   - Pode revogar documentos emitidos, atualizando imediatamente o status público para REVOGADO.
3. EMPRESA (Verificadora):
   - Consulta a autenticidade de documentos públicos através do código de 32 caracteres ou QR Code.
   - Acessa o conteúdo OCR e baixa arquivos originais de cidadãos exclusivamente enquanto o consentimento do titular estiver ativo e não expirado.

Diretrizes de resposta:
- Responda sempre em português do Brasil de forma concisa, educada e clara.
- Utilize formatação Markdown quando for útil (listas, negrito, etc.).
- Não revele segredos internos nem chaves criptográficas.
"""


def _gerar_resposta_local_assistente(
	mensagem: str,
	usuario_nome: str | None = None,
	usuario_perfil: str | None = None,
) -> str:
	"""Gera respostas inteligentes locais caso a chave de API da Anthropic não esteja configurada."""
	texto_minusculo = mensagem.lower()
	saudacao = f"Olá, {usuario_nome or 'usuário'}! " if usuario_nome else "Olá! "

	if any(termo in texto_minusculo for termo in ("consentimento", "compartilhar", "acesso", "empresa")):
		return (
			f"{saudacao}No Organiza AI, o controle é sempre seu (em conformidade com a LGPD).\n\n"
			"**Como funciona o consentimento:**\n"
			"1. Na tela **Acessos concedidos**, escolha o documento da sua carteira;\n"
			"2. Selecione a empresa parceira desejada;\n"
			"3. Defina a data e horário limite para expiração;\n"
			"4. A empresa só poderá visualizar e baixar o arquivo enquanto o prazo estiver ativo.\n\n"
			"Você pode **revogar o acesso a qualquer instante** com apenas um clique."
		)

	if any(termo in texto_minusculo for termo in ("emitir", "emissao", "lote", "instituicao", "qr code")):
		return (
			f"{saudacao}Instituições cadastradas podem emitir documentos digitais autênticos:\n\n"
			"- **Emissão Individual:** Informe o titular, título, tipo (diploma, certidão ou comprovante) e o conteúdo JSON.\n"
			"- **QR Code e Hash:** Cada emissão gera um código único de 32 caracteres e um QR Code para verificação instantânea.\n"
			"- **Emissão em Lote:** Envie arquivos `.csv` ou `.json` de até 10 MB para processamento assíncrono em segundo plano.\n"
			"- **Revogação:** Documentos emitidos podem ser revogados a qualquer momento informando o motivo."
		)

	if any(termo in texto_minusculo for termo in ("verificar", "valido", "autenticidade", "codigo")):
		return (
			f"{saudacao}A verificação de documentos no Organiza AI é rápida e pública:\n\n"
			"- Acesse **Verificar documento** e informe o código alfanumérico ou escaneie o QR Code;\n"
			"- O sistema verifica o hash criptográfico e retorna se o documento é **VÁLIDO**, **REVOGADO** ou **INVÁLIDO**;\n"
			"- A verificação pública preserva a privacidade do titular, exibindo apenas emissor, data e conformidade."
		)

	if any(termo in texto_minusculo for termo in ("documento", "carteira", "upload", "ocr", "guardar")):
		return (
			f"{saudacao}Na sua **Carteira Digital**, você pode:\n\n"
			"- Enviar arquivos PDF, PNG ou JPG de até 10 MB;\n"
			"- O sistema processa o texto automaticamente via OCR em português;\n"
			"- Classifica em diploma, certidão ou comprovante e extrai datas e emissores;\n"
			"- Permite busca rápida pelo conteúdo de qualquer documento armazenado."
		)

	return (
		f"{saudacao}Sou o assistente do **Organiza AI** (alimentado pelo modelo Anthropic Claude 3.5 Haiku).\n\n"
		"Posso te ajudar com dúvidas sobre:\n"
		"- Organização e envio de documentos na Carteira Digital;\n"
		"- Gestão de consentimentos e acessos conforme a LGPD;\n"
		"- Emissão de certificados, diplomas e lotes com QR Code;\n"
		"- Verificação e validação de autenticidade de documentos.\n\n"
		"Como posso te ajudar hoje?"
	)


async def processar_mensagem_chat(
	mensagem: str,
	historico: list[MensagemChat],
	usuario_nome: str | None = None,
	usuario_perfil: str | None = None,
) -> tuple[str, str]:
	"""Envia a conversa para a API da Anthropic Claude Haiku ou usa fallback assistido."""
	modelo = settings.anthropic_model or "claude-3-5-haiku-20241022"

	if not settings.anthropic_api_key:
		resposta_local = _gerar_resposta_local_assistente(
			mensagem, usuario_nome=usuario_nome, usuario_perfil=usuario_perfil
		)
		return resposta_local, modelo

	# Monta as mensagens no formato da API da Anthropic
	mensagens_api: list[dict[str, Any]] = []
	for msg in historico[-6:]:
		mensagens_api.append({"role": msg.role, "content": msg.content})
	mensagens_api.append({"role": "user", "content": mensagem})

	contexto_usuario = ""
	if usuario_nome or usuario_perfil:
		contexto_usuario = f"\nO usuário atual se chama '{usuario_nome or 'Usuário'}' e seu perfil no sistema é '{usuario_perfil or 'CIDADAO'}'."

	system_customizado = f"{SYSTEM_PROMPT}{contexto_usuario}"

	headers = {
		"x-api-key": settings.anthropic_api_key,
		"anthropic-version": "2023-06-01",
		"content-type": "application/json",
	}
	payload = {
		"model": modelo,
		"max_tokens": 1024,
		"system": system_customizado,
		"messages": mensagens_api,
	}

	try:
		async with httpx.AsyncClient(timeout=20.0) as client:
			resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
			resp.raise_for_status()
			data = resp.json()
			blocos_texto = [
				block.get("text", "")
				for block in data.get("content", [])
				if block.get("type") == "text"
			]
			resposta_texto = "\n".join(blocos_texto).strip()
			if resposta_texto:
				return resposta_texto, modelo
	except Exception as exc:
		logger.warning("Falha ao comunicar com a API Anthropic (%s). Usando fallback local.", exc)

	resposta_fallback = _gerar_resposta_local_assistente(
		mensagem, usuario_nome=usuario_nome, usuario_perfil=usuario_perfil
	)
	return resposta_fallback, modelo
