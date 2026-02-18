"""The ``kennabot healthcheck`` command.

Performs an HTTP GET against the local health endpoint and exits with a
zero status code on success or a non-zero code on failure.  Designed for
use as a container health check (Dockerfile HEALTHCHECK / podman --health-cmd).
"""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from kennabot.cli.async_typer import AsyncTyper

app = AsyncTyper(
    name="healthcheck",
    help="Check the health of the running KennaBot instance.",
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def healthcheck(
    host: Annotated[
        str,
        typer.Option("--host", help="Host to connect to."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", help="Port the health endpoint is listening on."),
    ] = 8080,
    path: Annotated[
        str,
        typer.Option("--path", help="Health endpoint path."),
    ] = "/health",
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Request timeout in seconds."),
    ] = 4.0,
) -> None:
    """Check the health of the running KennaBot instance.

    Exits 0 if the health endpoint returns HTTP 200, 1 otherwise.
    Designed to be used as a container health check.

    \b
    Examples:
        kennabot healthcheck
        kennabot healthcheck --port 9090
    """
    import httpx

    url = f"http://{host}:{port}{path}"
    try:
        response = httpx.get(url, timeout=timeout)
        if response.status_code == 200:
            typer.echo(f"healthy: {response.text.strip()}")
            raise typer.Exit(0)
        else:
            typer.echo(f"unhealthy: HTTP {response.status_code}", err=True)
            raise typer.Exit(1)
    except httpx.RequestError as exc:
        typer.echo(f"unhealthy: {exc}", err=True)
        sys.exit(1)
