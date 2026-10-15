"""Il preflight distingue la quota condivisa dal minimo per le riserve AWS."""

import runpy
from pathlib import Path

import pytest

readiness = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/aws_preflight.py"))[
    "concurrency_readiness"
]


@pytest.mark.parametrize(
    ("unreserved", "reserved", "supported", "required"),
    [
        (10, -1, True, 1),
        (0, -1, False, 1),
        (10, 1, False, 103),
        (102, 1, False, 103),
        (103, 1, True, 103),
        (103, 2, False, 106),
    ],
)
def test_lambda_quota_boundary(unreserved, reserved, supported, required):
    result = readiness(unreserved, reserved)
    assert result["configured_concurrency_supported"] is supported
    assert result["required_unreserved_before_deploy"] == required
