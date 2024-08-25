import nox

nox.needs_version = ">= 2024.4.15"

LINT_PYTHON_VERSION = "3.12"
BUILD_PYTHON_VERSIONS = ["3.12"]
TEST_PYTHON_VERSIONS = ["3.12"]

MYPY_VERSION = "~=1.11"
RUFF_VERSION = "~=0.6.2"

BUILD_VERSION = "~=1.2"


@nox.session(python=False)
def verify(session: nox.Session) -> None:
    """Run all verification tasks, including linting and tests."""

    # This is just a meta-session with no virtual environment.
    # We don't install anything here.
    session.notify("lint")
    session.notify("test")


@nox.session(python=False)
def lint(session: nox.Session) -> None:
    """Run all linting tools."""

    # This is just a meta-session with no virtual environment.
    # We don't install anything here.
    session.notify("ruff")
    session.notify("mypy")


@nox.session(python=LINT_PYTHON_VERSION)
def ruff(session: nox.Session) -> None:
    """Run the ruff linter."""
    session.install(f"ruff{RUFF_VERSION}")
    session.run("ruff", "check")
    session.run("ruff", "format", "--check")


@nox.session(python=LINT_PYTHON_VERSION)
def mypy(session: nox.Session) -> None:
    """Run the mypy type checker."""
    session.install(f"mypy{MYPY_VERSION}")
    session.install("--editable", ".[dev]")
    session.run("mypy")


@nox.session(python=TEST_PYTHON_VERSIONS)
def test(session: nox.Session) -> None:
    """Run all the tests with coverage."""
    session.install("--editable", ".[dev]")
    # for now, not bothering to keep more than one coverage report if we have multiple
    # Python versions...
    session.run("pytest", "--cov=video_tools", "--cov-report=html", "--cov-report=xml")


@nox.session(python=BUILD_PYTHON_VERSIONS)
def build(session: nox.Session) -> None:
    """Build the distribution files."""
    session.install(f"build{BUILD_VERSION}")
    session.run("python", "-m", "build")


@nox.session(python=LINT_PYTHON_VERSION, default=False)
def format(session: nox.Session) -> None:
    """Reformat code using ruff."""
    session.install(f"ruff{RUFF_VERSION}")
    session.run("ruff", "check", "--select", "I", "--fix")  # fix imports
    session.run("ruff", "format")
