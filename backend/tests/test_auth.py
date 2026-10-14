import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from scale_mobili.auth import authenticate
from scale_mobili.config import Settings
from scale_mobili.domain import DomainError


@pytest.fixture
def jwt_environment(monkeypatch):
    settings = Settings(
        mode="aws",
        core_table="test-core",
        events_table="test-events",
        public_url="https://prototype.example",
        cognito_issuer="https://issuer.example/pool",
        cognito_client_id="test-client",
        cursor_secret="test-only-" * 5,
    )
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client = SimpleNamespace(
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=key.public_key())
    )
    monkeypatch.setattr("scale_mobili.auth.jwks_client", lambda _: client)
    now = int(time.time())
    claims = {
        "exp": now + 300,
        "iat": now,
        "iss": settings.cognito_issuer,
        "aud": "https://prototype.example/mcp",
        "sub": "test-user",
        "token_use": "access",
        "client_id": "test-client",
        "scope": "openid scale-mobili/reports:write",
    }
    return settings, key, claims


def test_valid_access_token(jwt_environment):
    settings, key, claims = jwt_environment
    actor = authenticate("Bearer " + jwt.encode(claims, key, algorithm="RS256"), settings)
    assert actor.id == "test-user" and not actor.moderator
    assert actor.scopes == frozenset({"reports:write"})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("exp", 1),
        ("iss", "https://wrong.example"),
        ("aud", "other-resource"),
        ("token_use", "id"),
        ("client_id", "wrong-client"),
        ("iat", int(time.time()) + 86400),
    ],
)
def test_invalid_claims_rejected(jwt_environment, field, value):
    settings, key, claims = jwt_environment
    claims[field] = value
    with pytest.raises(DomainError, match="Token non valido"):
        authenticate("Bearer " + jwt.encode(claims, key, algorithm="RS256"), settings)


def test_demo_token_rejected_in_aws_mode(jwt_environment):
    settings, _, _ = jwt_environment
    with pytest.raises(DomainError):
        authenticate("Bearer demo-moderator", settings)


def test_demo_never_runs_on_lambda(monkeypatch):
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "test-function")
    with pytest.raises(ValueError, match="non può essere distribuita"):
        Settings(mode="demo")
