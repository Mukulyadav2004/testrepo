"""Nightly Spark batch job: latency/token-count anomaly detection across all traces.

Reads traces from PostgreSQL over JDBC, computes per (app_name, model_name) statistics,
flags traces whose latency_ms or token_count exceed mean + 2*stddev, and writes the
flagged traces to a PostgreSQL ``anomalies`` table.
"""
import os
from urllib.parse import urlparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

JDBC_DRIVER = "org.postgresql.Driver"


def jdbc_properties_from_url(database_url: str):
    """Convert a DATABASE_URL DSN into a (jdbc_url, properties) pair for Spark JDBC."""
    # Drop any SQLAlchemy async/sync driver suffix (e.g. postgresql+asyncpg://).
    scheme_stripped = database_url.replace("+asyncpg", "").replace("+psycopg2", "")
    parsed = urlparse(scheme_stripped)

    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    database = parsed.path.lstrip("/") or "agentobs"

    jdbc_url = f"jdbc:postgresql://{host}:{port}/{database}"
    properties = {
        "user": parsed.username or "agentobs",
        "password": parsed.password or "agentobs",
        "driver": JDBC_DRIVER,
    }
    return jdbc_url, properties


def detect_anomalies(traces_df):
    """Return a DataFrame of anomalous traces with an anomaly_reason column."""
    stats_df = traces_df.groupBy("app_name", "model_name").agg(
        F.mean("latency_ms").alias("mean_latency"),
        F.stddev("latency_ms").alias("std_latency"),
        F.mean("token_count").alias("mean_tokens"),
        F.stddev("token_count").alias("std_tokens"),
    )

    joined = traces_df.join(stats_df, on=["app_name", "model_name"], how="left")

    latency_threshold = F.col("mean_latency") + 2 * F.col("std_latency")
    token_threshold = F.col("mean_tokens") + 2 * F.col("std_tokens")

    latency_anomaly = F.col("latency_ms") > latency_threshold
    token_anomaly = F.col("token_count") > token_threshold

    # Build a human-readable reason; concat_ws drops the null branches.
    reason = F.concat_ws(
        "; ",
        F.when(latency_anomaly, F.lit("latency_ms above mean + 2*stddev")),
        F.when(token_anomaly, F.lit("token_count above mean + 2*stddev")),
    )

    anomalies = (
        joined.filter(latency_anomaly | token_anomaly)
        .withColumn("anomaly_reason", reason)
        .withColumn("detected_at", F.current_timestamp())
        .select(
            "trace_id",
            "app_name",
            "model_name",
            "latency_ms",
            "token_count",
            "anomaly_reason",
            "detected_at",
        )
    )
    return anomalies


def main():
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://agentobs:agentobs@localhost:5432/agentobs"
    )
    jdbc_url, properties = jdbc_properties_from_url(database_url)

    spark = SparkSession.builder.appName("trace-anomaly-detection").getOrCreate()
    try:
        traces_df = spark.read.jdbc(url=jdbc_url, table="traces", properties=properties)

        anomalies_df = detect_anomalies(traces_df)

        anomalies_df.write.jdbc(
            url=jdbc_url, table="anomalies", mode="append", properties=properties
        )

        print(f"Wrote {anomalies_df.count()} anomalies to PostgreSQL.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
