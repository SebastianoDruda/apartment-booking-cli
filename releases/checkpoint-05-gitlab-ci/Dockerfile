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
COPY apartment_booking/ ./apartment_booking/

USER booking

CMD ["python", "main.py"]

# Flask is installed only in the web/test targets; the CLI target stays dependency-free.
FROM base AS web-base
USER root
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
USER booking
CMD ["python", "-m", "flask", "--app", "apartment_booking.web:create_app", "--no-debug", "run", "--host", "0.0.0.0", "--port", "8000", "--no-debugger", "--no-reload"]

FROM web-base AS test
COPY tests/ ./tests/
RUN python -m unittest discover -s tests -v

FROM web-base AS web

FROM base AS runtime
