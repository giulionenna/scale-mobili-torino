"""Assegna il ruolo amministratore solo a un account con email già verificata."""

import argparse
import getpass
import json

import boto3


def grant_administrator(client, pool_id, email, *, check_only=False):
    email = email.strip()
    if not email or "@" not in email:
        raise ValueError("Indirizzo email richiesto")
    try:
        user = client.admin_get_user(UserPoolId=pool_id, Username=email)
    except client.exceptions.UserNotFoundException:
        return {"assigned": False, "ready": False, "reason": "account_not_found"}
    attributes = {item["Name"]: item["Value"] for item in user["UserAttributes"]}
    if (
        not user.get("Enabled")
        or user["UserStatus"] != "CONFIRMED"
        or attributes.get("email_verified") != "true"
        or attributes.get("email", "").casefold() != email.casefold()
    ):
        return {"assigned": False, "ready": False, "reason": "email_not_verified"}
    if check_only:
        return {"assigned": False, "ready": True}
    client.get_group(UserPoolId=pool_id, GroupName="administrators")
    # Usa l'identità immutabile restituita, non un alias email che potrebbe cambiare.
    client.admin_add_user_to_group(
        UserPoolId=pool_id, Username=user["Username"], GroupName="administrators"
    )
    return {"assigned": True, "ready": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-pool-id", required=True)
    parser.add_argument("--region", default="eu-south-1")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    email = getpass.getpass("Email dell’account (input nascosto): ")
    result = grant_administrator(
        boto3.client("cognito-idp", region_name=args.region),
        args.user_pool_id,
        email,
        check_only=args.check_only,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
