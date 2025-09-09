from litestar import Litestar

from .server.core import InitPlugin


def create_app() -> Litestar:
    """Create ASGI application."""
    return Litestar(plugins=[InitPlugin()])
