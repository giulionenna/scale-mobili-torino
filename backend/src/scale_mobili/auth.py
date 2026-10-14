from functools import lru_cache

import jwt

from scale_mobili.domain import Actor, DomainError


@lru_cache
def jwks_client(issuer):
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", timeout=5, cache_keys=True)


def authenticate(header, settings) -> Actor:
    if not header or not header.startswith("Bearer "):
        raise DomainError("Autenticazione richiesta", 401)
    token = header.removeprefix("Bearer ")
    if settings.mode == "demo":
        users = {"demo-user-1": False, "demo-user-2": False, "demo-moderator": True}
        if token not in users:
            raise DomainError("Identità demo non valida", 401)
        return Actor(id=token, moderator=users[token], scopes=frozenset({"reports:write"}))
    try:
        key = jwks_client(settings.cognito_issuer).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.cognito_issuer,
            audience=f"{settings.public_url.rstrip('/')}/mcp",
            options={"require": ["exp", "iat", "iss", "aud", "sub", "token_use", "client_id"]},
        )
        if claims["token_use"] != "access" or claims["client_id"] != settings.cognito_client_id:
            raise ValueError("Tipo o client del token non valido")
        scopes = frozenset(
            s.removeprefix("scale-mobili/")
            for s in claims.get("scope", "").split()
            if s.startswith("scale-mobili/")
        )
        return Actor(
            id=claims["sub"],
            moderator="moderators" in claims.get("cognito:groups", []),
            scopes=scopes,
        )
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise DomainError("Token non valido", 401) from exc


def challenge(settings):
    return (
        'Bearer resource_metadata="'
        + settings.public_url.rstrip("/")
        + '/.well-known/oauth-protected-resource/mcp", scope="scale-mobili/reports:write"'
    )
