from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent

from scale_mobili.auth import authenticate, challenge
from scale_mobili.config import Settings, get_settings
from scale_mobili.domain import CorrectionInput, DomainError, ReportInput
from scale_mobili.middleware import BodyLimitMiddleware
from scale_mobili.service import Service
from scale_mobili.store import DynamoStore, MemoryStore


def create_app(settings: Settings | None = None, store=None):
    settings = settings or get_settings()
    if store is None:
        store = (
            MemoryStore()
            if settings.mode == "demo"
            else DynamoStore(settings.core_table, settings.events_table, settings.region)
        )
    service = Service(store, settings.cursor_secret)
    hostname = urlparse(settings.public_url).netloc
    mcp = FastMCP(
        "Scale Mobili Torino — prova",
        instructions="Dati di prova sintetici. Identifica sempre l'impianto prima di scrivere.",
        stateless_http=True,
        json_response=True,
        streamable_http_path="/mcp",
        transport_security=TransportSecuritySettings(
            allowed_hosts=[hostname, "localhost:*", "127.0.0.1:*", "testserver"],
            allowed_origins=[settings.frontend_url, settings.public_url],
        ),
    )
    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_app):
        async with mcp.session_manager.run():
            yield

    app = FastAPI(title="Scale Mobili Torino", version="0.1.0", lifespan=lifespan)
    app.state.service, app.state.mcp, app.state.settings = service, mcp, settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )
    app.add_middleware(BodyLimitMiddleware)

    @app.exception_handler(DomainError)
    async def domain_error(_request, exc):
        headers = {"WWW-Authenticate": challenge(settings)} if exc.status_code == 401 else {}
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code, headers=headers)

    @app.middleware("http")
    async def cache_and_limits(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "mode": settings.mode,
            "synthetic_demo": settings.mode == "demo",
            "storage": "volatile_memory" if settings.mode == "demo" else "dynamodb",
        }

    @app.get("/.well-known/oauth-protected-resource/mcp")
    def protected_resource():
        return {
            "resource": settings.public_url.rstrip("/") + "/mcp",
            "authorization_servers": [settings.cognito_issuer] if settings.cognito_issuer else [],
            "scopes_supported": ["scale-mobili/reports:write"],
            "bearer_methods_supported": ["header"],
        }

    @app.get("/api/stations")
    def stations():
        return {"items": service.stations()}

    @app.get("/api/stations/{station_id}/escalators")
    def escalators(station_id: str):
        return {"items": service.escalators(station_id)}

    @app.get("/api/escalators/{escalator_id}/status")
    def status(escalator_id: str):
        return service.status(escalator_id)

    @app.get("/api/escalators/{escalator_id}/history")
    def history(
        escalator_id: str, cursor: str | None = None, limit: int = Query(default=20, ge=1, le=100)
    ):
        return service.history(escalator_id, cursor, limit)

    @app.post("/api/escalators/{escalator_id}/reports", status_code=201)
    def report(
        escalator_id: str,
        body: ReportInput,
        authorization: str | None = Header(None),
        idempotency_key: str | None = Header(None),
    ):
        return service.submit(
            escalator_id, body, authenticate(authorization, settings), idempotency_key
        )

    @app.post("/api/escalators/{escalator_id}/corrections", status_code=201)
    def correction(
        escalator_id: str,
        body: CorrectionInput,
        reference: str,
        authorization: str | None = Header(None),
        idempotency_key: str | None = Header(None),
    ):
        return service.submit(
            escalator_id,
            body,
            authenticate(authorization, settings),
            idempotency_key,
            "correction",
            reference,
        )

    @app.post("/api/escalators/{escalator_id}/confirmations", status_code=201)
    def confirmation(
        escalator_id: str,
        reference: str,
        authorization: str | None = Header(None),
        idempotency_key: str | None = Header(None),
    ):
        return service.submit(
            escalator_id,
            None,
            authenticate(authorization, settings),
            idempotency_key,
            "confirmation",
            reference,
        )

    @mcp.tool(annotations={"readOnlyHint": True})
    def list_stations() -> dict:
        """Elenca le stazioni: quelle fittizie sono contrassegnate synthetic."""
        return {"items": service.stations()}

    @mcp.tool(annotations={"readOnlyHint": True})
    def list_escalators(station_id: str) -> dict:
        """Elenca gli impianti confermati della stazione, senza inventare identità."""
        return {"items": service.escalators(station_id)}

    @mcp.tool(annotations={"readOnlyHint": True})
    def get_escalator_status(escalator_id: str) -> dict:
        """Stato con fonti separate: dato assente non significa funzionante."""
        return service.status(escalator_id)

    @mcp.tool(annotations={"readOnlyHint": True})
    def get_escalator_history(
        escalator_id: str, cursor: str | None = None, limit: int = 20
    ) -> dict:
        """Storico paginato per registrazione; i cursori non sono snapshot atomiche."""
        return service.history(escalator_id, cursor, limit)

    @mcp.tool(annotations={"readOnlyHint": False, "idempotentHint": True, "destructiveHint": False})
    def submit_escalator_report(
        escalator_id: str,
        status: str,
        idempotency_key: str,
        ctx: Context,
        observed_at: str | None = None,
    ) -> CallToolResult:
        """Invia una segnalazione autenticata: identifica prima l'impianto preciso.

        Mantieni la stessa idempotency_key e lo stesso contenuto nei ritentativi.
        """
        import json

        try:
            request = ctx.request_context.request
            actor = authenticate(
                request.headers.get("authorization") if request else None, settings
            )
            result = service.submit(
                escalator_id,
                ReportInput(status=status, observed_at=observed_at),
                actor,
                idempotency_key,
            )
            return CallToolResult(content=[TextContent(type="text", text=json.dumps(result))])
        except DomainError as exc:
            return CallToolResult(
                content=[TextContent(type="text", text=str(exc))],
                isError=True,
                _meta={"mcp/www_authenticate": [challenge(settings)]}
                if exc.status_code == 401
                else None,
            )

    app.mount("/", mcp_app)
    return app


def lambda_handler_factory(settings, store):
    def invoke(event, context):
        # Il manager MCP può essere avviato una sola volta: una nuova app per
        # invocazione evita il riuso del manager chiuso nelle invocazioni calde.
        # Archivio e configurazione restano condivisi; MCP è stateless.
        return Mangum(create_app(settings, store), lifespan="on")(event, context)

    return invoke


app = create_app()
handler = lambda_handler_factory(app.state.settings, app.state.service.store)
