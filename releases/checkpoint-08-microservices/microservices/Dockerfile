# Images of the microservices edition. Build from the release folder (Compose does
# this), so the shared domain package apartment_booking/ is part of the context.
#
# Each service has its own image, holding only its own package plus the shared
# ones, so the apartment and reservation teams build, test and ship independently:
#
#   docker build -f microservices/Dockerfile --target apartment-service .
#   docker build -f microservices/Dockerfile --target reservation-service .
#   docker build -f microservices/Dockerfile --target tools .     # CLI, importer, republish
#   docker build -f microservices/Dockerfile --target test .      # every unit and contract test
FROM python:3.14-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --gid 10001 dimora \
    && useradd --uid 10001 --gid dimora --no-log-init --create-home dimora

COPY microservices/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

# Shared by every service: the original domain rules and the platform package.
COPY apartment_booking/ ./apartment_booking/
COPY microservices/dimora/__init__.py ./dimora/__init__.py
COPY microservices/dimora/common/ ./dimora/common/

FROM base AS apartment-service
COPY microservices/dimora/apartment/ ./dimora/apartment/
USER dimora
CMD ["python", "-m", "dimora.apartment"]

FROM base AS reservation-service
COPY microservices/dimora/reservation/ ./dimora/reservation/
USER dimora
CMD ["python", "-m", "dimora.reservation"]

# Operational tools need both stores and the CLI.
FROM base AS tools
COPY microservices/dimora/ ./dimora/
USER dimora
CMD ["python", "-m", "dimora.cli"]

# Unit and contract tests run inside the image, against the exact runtime dependencies.
FROM tools AS test
USER root
COPY microservices/contracts/ ./contracts/
COPY microservices/tests/unit/ ./tests/unit/
COPY microservices/tests/contract/ ./tests/contract/
RUN python -m unittest discover -s tests/unit -v \
    && python -m unittest discover -s tests/contract -v
