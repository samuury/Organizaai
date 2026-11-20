# Organiza AI

Carteira digital para armazenar, emitir e verificar documentos e certificados.

## Requisitos

- Python 3.12+
- Node.js 20+
- Docker com Docker Compose
- Tesseract OCR com pacote de idioma português (`por`)

## Configuração

Na raiz do projeto, crie o arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

Suba o PostgreSQL:

```bash
docker compose up -d db
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

No Ubuntu/Debian, instale o mecanismo e os dados de idioma do OCR antes de iniciar
a API: `sudo apt install tesseract-ocr tesseract-ocr-por`. Os arquivos enviados
ficam por padrão em `backend/storage/`, fora da pasta pública do frontend.

A API ficará disponível em `http://localhost:8000`, a documentação interativa em
`http://localhost:8000/docs` e a verificação de saúde em `http://localhost:8000/health`.
Execute os testes do backend com `pytest` dentro de `backend/`.

### Frontend

Em outro terminal:

```bash
cd frontend
npm install
npm run dev
```

O Vite informará o endereço local do frontend. O teste inicial pode ser executado
com `npm test`.

## Estrutura

- `backend/app/modules/`: módulos de autenticação, carteira, emissão, verificação,
  consentimento, auditoria, dashboard e chat (assistente inteligente com Anthropic Claude 3.5 Haiku).
- `backend/alembic/`: configuração e versões das migrações do banco.
- `frontend/`: aplicação React, TypeScript e Tailwind CSS.
- `docker-compose.yml`: banco PostgreSQL para desenvolvimento local.

O módulo `wallet` aceita PDF, JPG e PNG até 10 MB, agenda OCR em segundo plano,
permite revisar os campos extraídos e oferece busca textual PostgreSQL. O módulo
`auth` fornece cadastro (`POST /auth/register`), login (`POST /auth/login`), dados
da conta (`GET /auth/me`), pesquisa de usuários/organizações (`GET /auth/users`) e
middleware de autenticação por JWT (via header `Authorization: Bearer <token>` ou
cookie de sessão `access_token`), estabelecendo `request.state.user_id`,
`request.state.role` e `request.state.institution_name`.

O módulo `issuance` permite emitir individualmente ou em lote; as rotas institucionais
esperam o perfil `INSTITUICAO` e utilizam o nome público da instituição salvo como emissor.

### Emissão institucional

`POST /issuance` recebe `usuario_id`, `titulo`, `tipo_documento` (`diploma`,
`certidao` ou `comprovante`) e `conteudo` como objeto JSON. A resposta inclui o
código, hash SHA-256, URL de verificação e URL do PNG do QR Code.

`POST /issuance/batch` aceita CSV ou JSON. O CSV usa cabeçalho
`usuario_id,titulo,tipo_documento,conteudo`, com `conteudo` codificado como objeto
JSON em cada célula. O JSON é uma lista dos mesmos objetos aceitos pela emissão
individual. A resposta imediata contém erros por linha e um `lote_id`; consulte
`GET /issuance/batch/{lote_id}` para acompanhar o processamento e obter os códigos
emitidos. A URL pública usada no QR Code é configurada por `API_PUBLIC_URL`.

A verificação pública tem limite de 60 consultas por minuto por IP. O padrão
`RATE_LIMIT_STORAGE_URI=memory://` é adequado para desenvolvimento com um processo;
em múltiplos workers, configure Redis nessa variável para compartilhar os limites.

### Alertas e dashboard

Alertas críticos podem ser entregues por SMTP (`SMTP_HOST`, `SMTP_PORT`,
`SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TO`, `SMTP_STARTTLS`) e/ou por
webhook (`CRITICAL_WEBHOOK_URL`, `CRITICAL_WEBHOOK_SECRET`). O webhook recebe os
headers `X-Organiza-Timestamp` e `X-Organiza-Signature`, calculados como
`sha256=` + HMAC-SHA256 do conteúdo `timestamp.corpo-json` usando o segredo.
`ALERT_WINDOW_MINUTES`, `OCR_MASS_FAILURE_THRESHOLD` e
`SUSPICIOUS_ACCESS_THRESHOLD` configuram as janelas e limiares. Alertas não incluem
conteúdo de documentos ou IP em claro.

`GET /dashboard/resumo` exige sessão autenticada e retorna documentos emitidos,
verificações, usuários ativos e tendência diária de 30 dias. A página inicial do
frontend apresenta esses indicadores e o gráfico; o middleware de autenticação
deve permitir a sessão por cookie e definir `request.state.user_id`.

### Consentimento de documentos

O middleware deve definir `request.state.user_id` e `request.state.role` como
`CIDADÃO` para conceder, revogar ou listar acessos, e como `EMPRESA` para ler um
documento compartilhado. O titular usa `POST /consent` com `documento_id`,
`empresa_id` e `expira_em` em ISO 8601 com fuso horário; `GET /consent` lista os
acessos ativos e `DELETE /consent/{consentimento_id}` os revoga. A empresa consulta
OCR/metadados em `GET /consent/documents/{documento_id}/content` ou baixa o original
em `/consent/documents/{documento_id}/download`; ambos retornam 404 sem consentimento
ativo.
