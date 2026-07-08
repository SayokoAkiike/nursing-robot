# PreCareBot backend API image (PR13).
#
# Uses the same requirements.txt as local/Codespaces development (rather
# than a separate slimmed-down requirements file) so this image installs
# exactly what's already known to work -- see README's Quick Start. That
# means it also pulls in perception/UI dependencies (opencv, pybullet,
# streamlit) the API itself doesn't need at runtime; build-essential/libpq-dev
# are here because pybullet and psycopg2 both compile from source on
# platforms without a prebuilt wheel. Trade-off: bigger image and slower
# build than a hand-trimmed dependency set, in exchange for zero risk of the
# container's dependency set silently drifting from what's actually tested.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# init_db() in backend/main.py's lifespan handler creates tables on boot if
# they don't exist (Base.metadata.create_all) -- fine for this local/demo
# compose setup. A real deployment should run `alembic upgrade head`
# explicitly as part of its own deploy step instead (see the comment on
# init_db() itself).
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
