"""AsyncTyper — a Typer subclass that supports async command functions."""

from __future__ import annotations

import asyncio
import inspect
from functools import wraps
from typing import Any

from typer import Typer


class AsyncTyper(Typer):
    """Drop-in replacement for typer.Typer that handles async commands.

    If a registered command function is a coroutine, it is automatically
    wrapped with asyncio.run() so typer/click can invoke it synchronously.
    Sync command functions pass through unchanged.
    """

    @staticmethod
    def _maybe_run_async(decorator: Any, f: Any) -> Any:
        if inspect.iscoroutinefunction(f):

            @wraps(f)
            def runner(*args: Any, **kwargs: Any) -> Any:
                return asyncio.run(f(*args, **kwargs))

            return decorator(runner)
        return decorator(f)

    def command(self, *args: Any, **kwargs: Any) -> Any:
        """Override to wrap async command functions."""
        decorator = super().command(*args, **kwargs)
        return lambda f: self._maybe_run_async(decorator, f)

    def callback(self, *args: Any, **kwargs: Any) -> Any:
        """Override to wrap async callback functions."""
        decorator = super().callback(*args, **kwargs)
        return lambda f: self._maybe_run_async(decorator, f)
