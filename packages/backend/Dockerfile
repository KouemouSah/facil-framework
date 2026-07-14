# Facil backend — minimal foundation (Phase D / D1).
FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal; asyncpg ships manylinux wheels (no compiler needed).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root runtime (k8s runAsNonRoot/runAsUser enforcement): dedicated uid/gid
# 1000, /app owned by it (writable workdir), and /tmp left world-writable
# (sticky bit) so libs that scratch-write there (tempfile, etc.) keep working.
RUN groupadd -g 1000 appuser \
    && useradd -u 1000 -g appuser -M -s /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app \
    && chmod 1777 /tmp

EXPOSE 8080

USER appuser

# The app runs as the least-privilege DB role (facil_app via DATABASE_URL).
# Schema migrations run SEPARATELY as a privileged role (db-init step):
#   alembic upgrade head      (DATABASE_URL = superuser)
# then the backend:
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
