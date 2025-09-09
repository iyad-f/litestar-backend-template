ARG PYTHON_BASE=3.13-slim-bookworm
ARG UV_BASE=python3.13-bookworm-slim

FROM ghcr.io/astral-sh/uv:${UV_BASE} AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

WORKDIR /project

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-install-project --no-dev

COPY --chown=65532:65532 . /project

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:${PYTHON_BASE}

LABEL org.opencontainers.image.title="litestar-backend-template" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.description="A backend template application built with Litestar" \
      org.opencontainers.image.source="https://github.com/iyad-f/litestar-backend-template" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.authors="Iyad"

RUN addgroup --system --gid 65532 nonroot \
    && adduser --no-create-home --system --uid 65532 --gid 65532 nonroot

USER nonroot:nonroot

WORKDIR /app

COPY --from=builder --chown=nonroot:nonroot /project /app

ENV PATH=/app/.venv/bin:$PATH PYTHONPATH=/app/src

EXPOSE 8000

ENTRYPOINT ["python", "-O", "-m", "app"]
CMD ["run"]
