# Organiza AI: Contexto do Projeto

Carteira digital de documentos e certificados (diplomas, certidões, comprovantes).
Três perfis: CIDADÃO (guarda documentos), INSTITUIÇÃO (emite documentos com QR Code),
EMPRESA (verifica autenticidade).

## Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2
- Banco: PostgreSQL (docker-compose para ambiente local)
- Frontend: React + Vite + TypeScript + Tailwind (responsivo)
- Arquivos: armazenamento local em dev, abstração para S3 em produção
- OCR: pytesseract (simples) com camada de serviço trocável
- Testes: pytest (backend), Vitest (frontend)

## Arquitetura
Monolito modular. Cada módulo em app/modules/<nome>/ com router.py, service.py,
models.py e schemas.py. Módulos: auth, wallet, issuance, verification, consent, audit, dashboard.

## Regras
- Código e comentários em português, nomes de variáveis em inglês
- Senhas com bcrypt, JWT com refresh token, RBAC por perfil, 2FA TOTP
- Toda alteração cadastral, emissão, revogação, consentimento e acesso a documento
  gera um registro na tabela audit_log (imutável: só INSERT)
- Dados sensíveis nunca aparecem em logs
- Respostas da API com tempo p95 abaixo de 300 ms
- LGPD: o titular controla quem acessa cada documento e por quanto tempo
- Sempre escrever testes para regras de negócio
- Tipagem completa e docstrings curtas