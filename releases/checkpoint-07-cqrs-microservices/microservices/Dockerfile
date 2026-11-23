# One image for every Python service of the event-driven edition; Compose picks
# the module to run. Build from the repository root (Compose does this), so the
# shared domain package apartment_booking/ is part of the context.
FROM python:3.14-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --gid 10001 dimora \
    && useradd --uid 10001 --gid dimora --no-log-init --create-home dimora

COPY microservices/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY apartment_booking/ ./apartment_booking/
COPY microservices/dimora/ ./dimora/

USER dimora
CMD ["python", "-m", "dimora.query"]

# Unit tests run inside the image, against the exact runtime dependencies.
FROM base AS test
COPY microservices/tests/unit/ ./tests/unit/
RUN python -m unittest discover -s tests/unit -v

FROM base AS runtime
