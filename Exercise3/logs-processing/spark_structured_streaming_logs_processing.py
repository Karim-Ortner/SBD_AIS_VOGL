from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, lower, count, window, to_timestamp
)
from pyspark.sql.functions import from_unixtime
from pyspark.sql.types import StructType, StructField, StringType, LongType

# 1. Configuration & Session Setup
CHECKPOINT_PATH = "/tmp/spark-checkpoints/activity3-logs-processing"

spark = (
    SparkSession.builder
    .appName("CrashEventsPerUser")
    .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_PATH)
    .getOrCreate()
)

spark.sparkContext.setLogLevel("ERROR")

# 2. Define schema (event timestamp is epoch seconds)
schema = StructType([
    StructField("timestamp", LongType()),
    StructField("status", StringType()),
    StructField("severity", StringType()),
    StructField("source_ip", StringType()),
    StructField("user_id", StringType()),
    StructField("content", StringType())
])

# 3. Read stream from Kafka
raw_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "kafka:9092")
    .option("subscribe", "logs")
    .option("startingOffsets", "earliest")
    .option("failOnDataLoss", "false")
    .load()
)

# 4. Parse JSON and convert event-time timestamp
parsed_df = (
    raw_df
    .select(from_json(col("value").cast("string"), schema).alias("data"))
    .select("data.*")
    # Convert epoch seconds → Spark timestamp (EVENT TIME)
    .withColumn(
        "event_time",
        # timestamp is epoch seconds -> convert to Spark timestamp
        to_timestamp(from_unixtime(col("timestamp")))
    )
)

# 5. Filter crash events (case-insensitive) and severity
filtered_df = (
    parsed_df.filter(
        (lower(col("content")).contains("crash")) &
        (col("severity").isin("High", "Critical"))
    )
)

# 6. Event-time windowed aggregation (10 seconds) with watermark
aggregated_df = (
    filtered_df
    .withWatermark("event_time", "30 seconds")
    .groupBy(
        window(col("event_time"), "10 seconds"),
        col("user_id")
    )
    .agg(count("*").alias("crash_count"))
)

# For debugging/visibility emit all windowed counts (adjust threshold as needed)
alerts_df = aggregated_df

# 8. Write results when windows complete
query = (
    alerts_df.writeStream
    .outputMode("update")
    .format("console")
    .option("truncate", "false")
    .option("numRows", 50)
    .option("checkpointLocation", CHECKPOINT_PATH)
    .trigger(processingTime="10 seconds")
    .start()
)

query.awaitTermination()
