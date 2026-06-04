# gRPC ingestion server.
# Build context: ./ingestion-server (the generated trace_pb2*.py stubs live here).
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Service code + generated proto stubs (trace_pb2.py, trace_pb2_grpc.py).
COPY . .

EXPOSE 50051

CMD ["python", "server.py"]
