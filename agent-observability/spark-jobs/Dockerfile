# Spark batch job for trace anomaly detection.
# Build context: ./spark-jobs
FROM bitnami/spark:3.5

WORKDIR /app

COPY anomaly_detection.py .

# Submit with the PostgreSQL JDBC driver on the classpath, e.g.:
#   spark-submit --packages org.postgresql:postgresql:42.7.3 /app/anomaly_detection.py
CMD ["spark-submit", "--packages", "org.postgresql:postgresql:42.7.3", "/app/anomaly_detection.py"]
