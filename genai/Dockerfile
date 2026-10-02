FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/genai

COPY genai/pyproject.toml ./pyproject.toml
COPY genai/app ./app

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["sh", "-c", "python -m app.gold_cache && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
