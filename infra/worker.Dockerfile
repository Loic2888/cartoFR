# syntax=docker/dockerfile:1
# Image du worker Python (contexte : worker/). Les données (data/, 19 Go) ne
# sont jamais copiées : elles sont montées en volume par docker-compose.yml.
# Le .dockerignore de cette image est worker.Dockerfile.dockerignore (à côté).

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY pyproject.toml ./
COPY cartofr ./cartofr
# uid 1000 : le même que le propriétaire de data/ sur l'hôte.
RUN pip install . && useradd --create-home --uid 1000 cartofr
USER cartofr
CMD ["python", "-m", "cartofr"]
