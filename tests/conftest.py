from typing import cast

import pytest


# CLI options and fixtures for the integration tests.  They must be in the root tests directory in
# order for "pytest --help" to correctly list them.
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--write-debug",
        action="store_true",
        help="Write debug files.",
    )


@pytest.fixture
def write_debug(request: pytest.FixtureRequest) -> str:
    return cast(str, request.config.getoption("--write-debug"))
