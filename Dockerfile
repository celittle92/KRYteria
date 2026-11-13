# KRYteria — one image, one process, one port.
#
# The app already serves its own built front end (backend/main.py mounts frontend/dist),
# so there is no second service, no reverse proxy and no CORS to configure. That is the
# same property that makes the ten-minute local setup work, reused.
#
# Why a Dockerfile rather than a platform's Python buildpack: this pins the interpreter.
# The project is developed on 3.14, most hosts still default to 3.11 or 3.12, and
# "works on my machine, wrong minor version in production" is the single most common way
# a deadline deploy fails. An image removes the question.
#
# Build and run locally (identical to what the host does):
#     docker build -t kryteria .
#     docker run -p 8000:8000 -e KRYTERIA_MODE=demo -e KRYTERIA_SEED_ON_BOOT=true kryteria
#     open http://localhost:8000

# ---------------------------------------------------------------- build stage
# Compilers live here and are thrown away. pwdlib[argon2] and tiktoken normally install
# from wheels; when a wheel is missing for a platform, this stage can still build it,
# which is the difference between a slow deploy and a failed one.
FROM python:3.14-slim AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install -r requirements.txt

# ---------------------------------------------------------------- runtime
FROM python:3.14-slim AS runtime

# Never run as root. A journalling app holding other people's intimate writing does not
# get to be casual about this, even on a class deployment.
RUN useradd --create-home --uid 10001 kryteria

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    KRYTERIA_HOST=0.0.0.0 \
    PORT=8000 \
    # The demo must exist however often the host recycles the process. See
    # backend/main._seed_on_boot.
    KRYTERIA_SEED_ON_BOOT=true

COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY --chown=kryteria:kryteria . .

# The database lives outside the source tree so a mounted volume can own it, and so a
# redeploy that replaces /app does not quietly replace somebody's journal.
ENV KRYTERIA_DB_PATH=/data/kryteria.db
RUN mkdir -p /data && chown kryteria:kryteria /data
VOLUME ["/data"]

USER kryteria
EXPOSE 8000

# Honour $PORT: hosts assign one and expect the process to use it.
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
