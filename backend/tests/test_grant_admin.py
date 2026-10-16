"""Bootstrap del ruolo: nessun invito, password, email o credenziale nei log."""

import importlib.util
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "grant_admin", Path(__file__).resolve().parents[2] / "scripts/grant_admin.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MissingUser(Exception):
    pass


class Client:
    exceptions = SimpleNamespace(UserNotFoundException=MissingUser)

    def __init__(self):
        self.calls = []
        self.user = {
            "Username": "immutable-user-id",
            "Enabled": True,
            "UserStatus": "CONFIRMED",
            "UserAttributes": [
                {"Name": "email", "Value": "synthetic@example.invalid"},
                {"Name": "email_verified", "Value": "true"},
            ],
        }

    def admin_get_user(self, **kwargs):
        if self.user is None:
            raise MissingUser()
        return deepcopy(self.user)

    def get_group(self, **kwargs):
        self.calls.append(("get_group", kwargs))

    def admin_add_user_to_group(self, **kwargs):
        self.calls.append(("grant", kwargs))


def test_verified_account_granted_using_immutable_username():
    client = Client()
    assert module.grant_administrator(client, "pool", "synthetic@example.invalid")["assigned"]
    assert client.calls[-1] == (
        "grant",
        {
            "UserPoolId": "pool",
            "Username": "immutable-user-id",
            "GroupName": "administrators",
        },
    )


@pytest.mark.parametrize(
    "problem", ["missing", "unconfirmed", "disabled", "unverified", "different_email"]
)
def test_never_promotes_unverified_or_wrong_account(problem):
    client = Client()
    if problem == "missing":
        client.user = None
    elif problem == "unconfirmed":
        client.user["UserStatus"] = "UNCONFIRMED"
    elif problem == "disabled":
        client.user["Enabled"] = False
    elif problem == "unverified":
        client.user["UserAttributes"][1]["Value"] = "false"
    else:
        client.user["UserAttributes"][0]["Value"] = "someone-else@example.invalid"
    result = module.grant_administrator(client, "pool", "synthetic@example.invalid")
    assert not result["assigned"] and not result["ready"] and not client.calls


def test_check_only_has_no_writes():
    client = Client()
    assert module.grant_administrator(
        client, "pool", "synthetic@example.invalid", check_only=True
    ) == {"assigned": False, "ready": True}
    assert not client.calls
