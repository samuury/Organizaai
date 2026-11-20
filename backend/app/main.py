"""Ponto de entrada da API."""

from fastapi import FastAPI, Request
from fastapi.responses import Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.background import BackgroundTask
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.database import SessionLocal
from app.core.notifications import notificar_tentativas_suspeitas
from app.modules.audit.service import registrar_auditoria
from app.modules.auth.router import router as auth_router
from app.modules.auth.service import decodificar_token_jwt
from app.modules.chat.router import router as chat_router
from app.modules.consent.router import router as consent_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.issuance.router import router as issuance_router
from app.modules.verification.router import router as verification_router
from app.modules.wallet.router import router as wallet_router

app = FastAPI(title="Organiza AI", version="0.1.0")
cors_origins = list(
    {
        settings.frontend_origin,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.limiter = limiter
app.state.audit_session_factory = SessionLocal


@app.middleware("http")
async def autenticar_requisicao_middleware(request: Request, call_next):
    """Extrai credenciais do token JWT e popula o request.state."""
    request.state.user_id = None
    request.state.role = None
    request.state.institution_name = None

    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if token:
        try:
            payload = decodificar_token_jwt(token)
            request.state.user_id = int(payload["sub"])
            request.state.role = payload.get("perfil")
            request.state.institution_name = payload.get("nome")
        except Exception:
            request.state.user_id = None
            request.state.role = None
            request.state.institution_name = None

    return await call_next(request)


def rate_limit_exceeded_handler(request: Request, error: RateLimitExceeded) -> Response:
    """Registra tentativa de verificação bloqueada e retorna HTTP 429."""
    session_factory = getattr(request.app.state, "audit_session_factory", SessionLocal)
    if request.url.path.startswith("/verificar/"):
        with session_factory() as session:
            try:
                registrar_auditoria(
                    session,
                    usuario_id=None,
                    acao="verification.rate_limited",
                    entidade="issued_documents",
                    entidade_id=request.path_params.get("codigo", "unknown"),
                    dados_depois={"status": "RATE_LIMITED"},
                    ip=request.client.host if request.client else None,
                )
                session.commit()
            except Exception:
                session.rollback()
    response = _rate_limit_exceeded_handler(request, error)
    if request.url.path.startswith("/verificar/"):
        response.background = BackgroundTask(
            notificar_tentativas_suspeitas,
            request.client.host if request.client else None,
            session_factory,
        )
    return response


app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(issuance_router)
app.include_router(verification_router)
app.include_router(consent_router)
app.include_router(dashboard_router)
app.include_router(wallet_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Informa que a API está disponível."""
    return {"status": "ok"}
