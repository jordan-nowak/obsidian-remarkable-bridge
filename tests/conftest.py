"""
Shared fixtures and CLI options for functional tests.

- real_config  : loads config.test.yaml (session-scoped)
- --functional : required flag to run functional tests; without it, all tests in
                 tests/functional/ are skipped automatically.
"""

import pytest
import yaml


def pytest_addoption(parser):
    parser.addoption(
        "--functional",
        action="store_true",
        default=False,
        help="Run functional tests requiring real hardware",
    )


@pytest.fixture(scope="session")
def real_config():
    """Load the actual configuration from config.yaml."""
    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(autouse=True)
def skip_if_not_functional(request):
    """Skip all tests in the functional/ directory unless --functional is passed."""
    if "functional" in str(request.fspath) and not request.config.getoption("--functional"):
        pytest.skip("Pass --functional to run these tests")
