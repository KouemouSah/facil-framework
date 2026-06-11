# Facil backend — minimal foundation (Phase D / D1).
FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal; asyncpg ships manylinux wheels (no compiler needed).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# The app runs as the least-privilege DB role (facil_app via DATABASE_URL).
# Schema migrations run SEPARATELY as a privileged role (db-init step):
#   alembic upgrade head      (DATABASE_URL = superuser)
# then the backend:
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
