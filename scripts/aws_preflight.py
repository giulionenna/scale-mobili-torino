"""Verifiche AWS in sola lettura, senza stampare identità o credenziali.

Esecuzione: uv run --project backend python scripts/aws_preflight.py
La policy del proxy resta vincolante. Gli endpoint non consentiti sono saltati.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

REGION = "eu-south-1"
CONFIG = Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 0})


def policy():
    file = Path("/etc/codex/network-policy.json")
    if not file.exists():
        return set(), False
    data = json.loads(file.read_text())
    if data.get("version") != 1:
        return set(), False
    network = data.get("http_network_policy", {})
    return {r["host"] for r in network.get("egress_rules", [])}, (
        network.get("type") == "unrestricted"
    )


def concurrency_readiness(unreserved, reserved_per_function):
    required = 3 * max(reserved_per_function, 0)
    return {
        "mode": "shared" if reserved_per_function == -1 else "reserved",
        "reserved_per_function": reserved_per_function,
        "required_new_reservations": required,
        "required_unreserved_before_deploy": 100 + required if required else 1,
        "configured_concurrency_supported": (
            unreserved >= 100 + required if required else unreserved > 0
        ),
    }


def main(reserved_concurrency=-1):
    hosts, unrestricted = policy()
    results = {}

    def check(name, service, region, operation, summarize, endpoint=None):
        kwargs = {"region_name": region, "config": CONFIG}
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        client = boto3.client(service, **kwargs)
        host = urlparse(client.meta.endpoint_url).hostname
        if not unrestricted and host not in hosts:
            results[name] = {"state": "network_policy_pending", "required_host": host}
            return
        try:
            response = operation(client)
            results[name] = {"state": "verified_read_only", **summarize(response)}
        except ClientError as exc:
            results[name] = {
                "state": "not_verified",
                "error_code": exc.response["Error"]["Code"],
                "required_host": host,
            }
        except (BotoCoreError, OSError) as exc:
            # Non stampare messaggi SDK: possono includere URL, identità o token.
            results[name] = {
                "state": "not_verified",
                "error_type": type(exc).__name__,
                "required_host": host,
            }

    check(
        "identity",
        "sts",
        "us-east-1",
        lambda c: c.get_caller_identity(),
        lambda r: {"principal_kind": r["Arn"].split(":", 5)[-1].split("/")[0]},
        endpoint="https://sts.amazonaws.com",
    )
    check(
        "region",
        "account",
        "us-east-1",
        lambda c: c.get_region_opt_status(RegionName=REGION),
        lambda r: {"region": REGION, "opt_status": r.get("RegionOptStatus")},
    )
    check(
        "oidc",
        "iam",
        "us-east-1",
        lambda c: c.list_open_id_connect_providers(),
        lambda r: {"provider_count": len(r.get("OpenIDConnectProviderList", []))},
    )

    def dynamodb_usage(client):
        tables = []
        for page in client.get_paginator("list_tables").paginate():
            tables.extend(page["TableNames"])
        read, write, size, index_count, on_demand = 0, 0, 0, 0, 0
        for name in tables:
            table = client.describe_table(TableName=name)["Table"]
            read += table.get("ProvisionedThroughput", {}).get("ReadCapacityUnits", 0)
            write += table.get("ProvisionedThroughput", {}).get("WriteCapacityUnits", 0)
            size += table.get("TableSizeBytes", 0)
            on_demand += (
                table.get("BillingModeSummary", {}).get("BillingMode")
                == "PAY_PER_REQUEST"
            )
            for index in table.get("GlobalSecondaryIndexes", []):
                index_count += 1
                read += index.get("ProvisionedThroughput", {}).get(
                    "ReadCapacityUnits", 0
                )
                write += index.get("ProvisionedThroughput", {}).get(
                    "WriteCapacityUnits", 0
                )
                size += index.get("IndexSizeBytes", 0)
        return {
            "tables": len(tables),
            "indexes": index_count,
            "allocated_rcu": read,
            "allocated_wcu": write,
            "approximate_bytes": size,
            "on_demand_tables": on_demand,
        }

    check("dynamodb_usage", "dynamodb", REGION, dynamodb_usage, lambda r: r)

    def free_tier(client):
        offers = []
        args = {"maxResults": 100}
        while True:
            page = client.get_free_tier_usage(**args)
            offers.extend(page.get("freeTierUsages", []))
            if not page.get("nextToken"):
                break
            args["nextToken"] = page["nextToken"]
        return {
            "offers_reported": len(offers),
            "relevant_offers": [
                {
                    field: item.get(field)
                    for field in (
                        "service",
                        "usageType",
                        "operation",
                        "region",
                        "limit",
                        "actualUsageAmount",
                        "forecastedUsageAmount",
                        "unit",
                        "freeTierType",
                    )
                }
                for item in offers
                if any(
                    service in item.get("service", "").lower()
                    for service in (
                        "dynamo",
                        "cognito",
                        "lambda",
                        "s3",
                        "cloudwatch",
                        "gateway",
                    )
                )
            ],
            "coverage_verified": False,
            "note": "Le offerte vanno confrontate con consumi, crediti e payer account.",
        }

    check("free_tier", "freetier", "us-east-1", free_tier, lambda r: r)
    check(
        "account_plan",
        "freetier",
        "us-east-1",
        lambda c: c.get_account_plan_state(),
        lambda r: {
            "plan_type": r.get("accountPlanType"),
            "plan_status": r.get("accountPlanStatus"),
            "remaining_credits": r.get("accountPlanRemainingCredits"),
            "expires_at": str(r.get("accountPlanExpirationDate")),
        },
    )
    check(
        "lambda_quota",
        "lambda",
        REGION,
        lambda c: c.get_account_settings(),
        lambda r: {
            "concurrent_executions": r["AccountLimit"]["ConcurrentExecutions"],
            "unreserved_concurrency": r["AccountLimit"][
                "UnreservedConcurrentExecutions"
            ],
            "function_count": r.get("AccountUsage", {}).get("FunctionCount"),
            "code_storage_bytes": r.get("AccountUsage", {}).get("TotalCodeSize"),
            "minimum_unreserved_for_reservations": 100,
            **concurrency_readiness(
                r["AccountLimit"]["UnreservedConcurrentExecutions"],
                reserved_concurrency,
            ),
        },
    )
    check(
        "lambda_service_quota",
        "service-quotas",
        REGION,
        lambda c: c.get_service_quota(ServiceCode="lambda", QuotaCode="L-B99A9384"),
        lambda r: {
            "value": r["Quota"]["Value"],
            "adjustable": r["Quota"]["Adjustable"],
        },
    )
    check(
        "pricing_access",
        "pricing",
        "us-east-1",
        lambda c: c.describe_services(ServiceCode="AmazonDynamoDB"),
        lambda r: {
            "pricing_endpoint_accessible": bool(r.get("Services")),
            "milan_rates_verified": False,
        },
    )
    for name, service, method, args, field in [
        ("cognito", "cognito-idp", "list_user_pools", {"MaxResults": 60}, "UserPools"),
        ("http_api", "apigatewayv2", "get_apis", {"MaxResults": "100"}, "Items"),
        ("lambda", "lambda", "list_functions", {"MaxItems": 50}, "Functions"),
        ("logs", "logs", "describe_log_groups", {"limit": 50}, "logGroups"),
        ("scheduler", "scheduler", "list_schedules", {"MaxResults": 100}, "Schedules"),
    ]:
        check(
            name,
            service,
            REGION,
            lambda c, method=method, args=args: getattr(c, method)(**args),
            lambda r, field=field: {
                "first_page_count": len(r.get(field, [])),
                "full_inventory_verified": False,
            },
        )
    blockers = []
    lambda_quota = results["lambda_quota"]
    if lambda_quota.get("state") != "verified_read_only":
        blockers.append("lambda_concurrency_not_verified")
    elif not lambda_quota["configured_concurrency_supported"]:
        blockers.append("lambda_configured_concurrency_unavailable")
    print(
        json.dumps(
            {
                "checked_at": datetime.now(UTC).isoformat(),
                "region": REGION,
                "resources_created": False,
                "budget_verified": False,
                "deployment_blockers": blockers,
                "checks": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reserved-concurrency", type=int, choices=[-1, 1, 2, 3, 4, 5], default=-1
    )
    main(parser.parse_args().reserved_concurrency)
