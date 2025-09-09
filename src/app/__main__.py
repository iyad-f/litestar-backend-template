from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from litestar.cli import litestar_group

from app.config import APP_CONFIG

if TYPE_CHECKING:
    from typing import NoReturn

__all__ = ("run_cli",)


def run_cli() -> NoReturn:
    """Application Entrypoint."""
    os.environ.setdefault("LITESTAR_APP", APP_CONFIG.loc)
    os.environ.setdefault("LITESTAR_APP_NAME", APP_CONFIG.name)
    os.environ.setdefault("LITESTAR_HOST", APP_CONFIG.server.host)
    os.environ.setdefault("LITESTAR_PORT", str(APP_CONFIG.server.port))
    os.environ.setdefault("LITESTAR_DEBUG", str(int(APP_CONFIG.debug)))
    sys.exit(litestar_group())  # pyright: ignore[reportUnknownArgumentType]


if __name__ == "__main__":
    run_cli()
