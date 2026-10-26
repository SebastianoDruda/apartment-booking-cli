FROM python:3.14-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APARTMENT_BOOKING_DB_PATH=/data/apartment_booking.db

WORKDIR /app

RUN groupadd --gid 10001 booking \
    && useradd --uid 10001 --gid booking --no-log-init --create-home booking \
    && mkdir /data \
    && chown booking:booking /data

COPY main.py ./
COPY src/ ./src/

USER booking

CMD ["python", "main.py"]

# Run the same test suite inside the image without shipping tests in production.
FROM base AS test
COPY tests/ ./tests/
RUN python -m unittest discover -s tests -v

FROM base AS runtime
