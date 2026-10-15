import json

from fastapi.encoders import jsonable_encoder
from mcp.server.fastmcp import Context
from mcp.types import CallToolResult, TextContent
from pydantic import ValidationError

from scale_mobili.auth import authenticate, challenge
from scale_mobili.domain import DeviceReportInput, DomainError, ProposalInput


def register_tools(mcp, service, settings):
    def authorized(ctx, action):
        try:
            request = ctx.request_context.request
            actor = authenticate(
                request.headers.get("authorization") if request else None,
                settings,
                require_resource=True,
            )
            value = action(actor)
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(jsonable_encoder(value)))]
            )
        except (DomainError, ValidationError) as exc:
            return CallToolResult(
                content=[TextContent(type="text", text=str(exc))],
                isError=True,
                _meta={"mcp/www_authenticate": [challenge(settings)]}
                if isinstance(exc, DomainError) and exc.status_code == 401
                else None,
            )

    @mcp.tool(annotations={"readOnlyHint": True})
    def list_devices(station_id: str) -> dict:
        """Scale mobili e ascensori confermati; gli ID interni non sono ID GTT."""
        return {"items": service.devices(station_id)}

    @mcp.tool(annotations={"readOnlyHint": True})
    def get_working_percentage() -> dict:
        """Quota dell'ultima osservazione funzionante sul censimento, con copertura."""
        return service.availability()

    @mcp.tool(annotations={"readOnlyHint": True})
    def get_private_statistics(ctx: Context) -> CallToolResult:
        """Richiede login e stats:read: confronto ufficiale/community, nuovi fermi e streak."""
        return authorized(ctx, service.private_statistics)

    @mcp.tool(annotations={"readOnlyHint": False, "idempotentHint": True, "destructiveHint": False})
    def submit_device_report(
        device_id: str,
        station_id: str,
        status: str,
        idempotency_key: str,
        ctx: Context,
        observed_at: str | None = None,
        description: str = "",
    ) -> CallToolResult:
        """Segnala un impianto preciso con stazione obbligatoria. Mantieni la chiave nei retry."""
        return authorized(
            ctx,
            lambda actor: service.submit(
                device_id,
                DeviceReportInput(
                    station_id=station_id,
                    status=status,
                    observed_at=observed_at,
                    description=description,
                ),
                actor,
                idempotency_key,
            ),
        )

    @mcp.tool(annotations={"readOnlyHint": False, "idempotentHint": True, "destructiveHint": False})
    def propose_device(
        station_id: str,
        kind: str,
        name: str,
        location: str,
        idempotency_key: str,
        ctx: Context,
        description: str = "",
    ) -> CallToolResult:
        """Propone scala_mobile o ascensore. Non entra nel censimento prima dell'approvazione."""
        return authorized(
            ctx,
            lambda actor: service.propose(
                ProposalInput(
                    station_id=station_id,
                    kind=kind,
                    name=name,
                    location=location,
                    description=description,
                ),
                actor,
                idempotency_key,
            ),
        )
