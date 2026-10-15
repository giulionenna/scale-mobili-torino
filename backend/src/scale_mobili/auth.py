from functools import lru_cache

import jwt

from scale_mobili.domain import Actor, DomainError


def oauth_scope_prefix(settings):
    return settings.public_url.rstrip("/") + "/mcp/"


def oauth_scopes(settings):
    prefix = oauth_scope_prefix(settings)
    return [prefix + "reports:write", prefix + "stats:read"]


@lru_cache
def jwks_client(issuer):
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", timeout=5, cache_keys=True)


def authenticate(header, settings, *, require_resource=False) -> Actor:
    if not header or not header.startswith("Bearer "):
        raise DomainError("Autenticazione richiesta", 401)
    token = header.removeprefix("Bearer ")
    if settings.mode != "aws":
        users = {"demo-user-1": False, "demo-user-2": False, "demo-moderator": True}
        if token not in users:
            raise DomainError("Identità demo non valida", 401)
        return Actor(
            id=token, moderator=users[token], scopes=frozenset({"reports:write", "stats:read"})
        )
    try:
        key = jwks_client(settings.cognito_issuer).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.cognito_issuer,
            audience=f"{settings.public_url.rstrip('/')}/mcp",
            options={
                "require": ["exp", "iat", "iss", "sub", "token_use", "client_id"]
                + (["aud"] if require_resource else []),
                "verify_aud": False,
            },
        )
        if claims["token_use"] != "access" or claims["client_id"] not in [
            settings.cognito_client_id,
            *settings.additional_client_ids,
        ]:
            raise ValueError("Tipo o client del token non valido")
        # Cognito REST può emettere access token senza aud. Se presente deve
        # corrispondere alla risorsa; per MCP il binding aud è obbligatorio.
        if "aud" in claims and claims["aud"] != f"{settings.public_url.rstrip('/')}/mcp":
            raise ValueError("Audience non valida")
        prefix = oauth_scope_prefix(settings)
        scopes = frozenset(
            s.removeprefix(prefix) for s in claims.get("scope", "").split() if s.startswith(prefix)
        )
        return Actor(
            id=claims["sub"],
            moderator="moderators" in claims.get("cognito:groups", []),
            scopes=scopes,
        )
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise DomainError("Token non valido", 401) from exc


def challenge(settings):
    return (
        'Bearer resource_metadata="'
        + settings.public_url.rstrip("/")
        + '/.well-known/oauth-protected-resource/mcp", scope="'
        + oauth_scopes(settings)[0]
        + '"'
    )
