# syntax=docker/dockerfile:1
# ---- build stage: compile wheels with build tools that never reach the runtime image ----
FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /src
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ---- runtime stage: minimal, non-root, read-only friendly ----
FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/SunnGHubX/sunn-platform-lab" \
      org.opencontainers.image.description="Secure front door for OpenAI-compatible model servers" \
      org.opencontainers.image.licenses="MIT"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
COPY --from=build /install /usr/local
WORKDIR /app
COPY app/ ./app/
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["uvicorn", "--factory", "app.main:app_factory", "--host", "0.0.0.0", "--port", "8080", "--no-server-header"]
