# REST API server.
#
# Build context: the repository root (.), because main.py imports the evaluator's
# handler inline (POST /traces/{id}/evaluate), so the evaluator package and its
# dependencies must be present in the image.
#
# Build with:
#   docker build -f api-server/Dockerfile -t agentobs-api .
FROM python:3.11-slim

WORKDIR /app

COPY api-server/requirements.txt ./api-server/requirements.txt
COPY evaluator/requirements.txt ./evaluator/requirements.txt
RUN pip install --no-cache-dir \
        -r api-server/requirements.txt \
        -r evaluator/requirements.txt

COPY api-server/ ./api-server/
COPY evaluator/ ./evaluator/

WORKDIR /app/api-server

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
