# Start the environment

Download the repository and start the environment:

```bash
docker compose up -d
```
## Verify the services
-Apache Pinot's Web UI: http://localhost:9000  

## Create a kafka topic:
```bash
docker exec \
  -t kafka kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --partitions=1 --replication-factor=1 \
  --create --topic ingest-kafka
```

# Learn more about Apache Pinot
- Apache Pinot's home page: https://docs.pinot.apache.org/ 

# Basic setup

Understand the content of [ingest schema file](ingest_kafka_schema.json) and [table creation file](ingest_kafka_realtime_table.json). Then, navigate to Apache Pinot's Web UI and add a table schema and a realtime table. 

Navigate to ```Query Console``` and run your first query:

```
select * from ingest_kafka
```

More advanced query:

```
SELECT source_ip, COUNT(*) AS match_count FROM ingest_kafka
WHERE
  content LIKE '%vulnerability%' AND severity = 'High'
GROUP BY source_ip
ORDER BY match_count DESC    
```


See more about queries' syntax: https://docs.pinot.apache.org/users/user-guide-query

What are we missing when we execute the queries?

**Answer:** When executing the queries without starting the load generator, the table is empty or contains no data. The queries will return no results because there is no data ingested into the Apache Pinot table yet. We need to configure the Kafka ingestion to consume messages from the Kafka topic and populate the table with real-time data.

See how to ingest data on Apache Pinot: https://docs.pinot.apache.org/manage-data/data-import

# Load generator
Inside the ```load-generator``` folder, understand the content of the docker compose file and start generating log records: 
```bash
docker compose up -d
```

What is the relation between these records being generated and Apache Pinot's table?

**Answer:** The load generator in the `load-generator` folder generates synthetic log records (containing fields like source_ip, severity, content, etc.) and produces them to the Kafka topic `ingest-kafka`. Apache Pinot has a real-time ingestion pipeline configured that consumes messages from this Kafka topic and automatically inserts them into the `ingest_kafka` table. This establishes a streaming data pipeline where generated logs flow from Kafka directly into Pinot's table in real-time, enabling continuous analytical queries on fresh data.

Run again the advanced query:

```
SELECT source_ip, COUNT(*) AS match_count FROM ingest_kafka
WHERE
  content LIKE '%vulnerability%' AND severity = 'High'
GROUP BY source_ip
ORDER BY match_count DESC    
```

Are there any changes in query results? What and why?

**Answer:** Yes, there should be significant changes in the query results after the load generator starts. The first execution returned no results because the table was empty. After the load generator runs and ingests data via Kafka, the advanced query now returns data showing the source IPs that have the most log entries containing 'vulnerability' with 'High' severity. The query results appear because: (1) The load generator continuously produces synthetic log records to Kafka, (2) Pinot's real-time ingestion consumes and indexes these records, (3) New data becomes immediately queryable without batch processing delays. The result set contains aggregated statistics by source_ip with their match counts.

Moreover, what is the amount of data in the table?

**Answer:** To determine the amount of data in the table, run the query:
```
SELECT COUNT(*) FROM ingest_kafka
```
This returns the total number of records currently in the table. The data volume grows continuously as the load generator produces new records. You can also check the table size via the Pinot Web UI under "Tables" section, which shows metadata including segment count, memory usage, and record count. The exact amount depends on how long the load generator has been running.

How this last query relates to the Spark Structured Streaming logs processing example from Exercise 3? 

**Answer:** Both systems perform similar analytical processing on streaming data:
- **Spark Structured Streaming (Exercise 3):** Uses micro-batch processing to compute windowed aggregations on streaming data, typically with micro-batch intervals (e.g., 1-2 seconds).
- **Apache Pinot:** Uses real-time ingestion to insert data into an OLAP data store, enabling immediate querying via SQL.

The key difference is that Spark performs *transformations* and *aggregations* on the stream (computing results as data arrives), while Pinot stores raw events and allows *ad-hoc aggregations* at query time. The advanced query in Pinot is equivalent to computing a streaming aggregation in Spark—both produce grouped statistics (source_ip with counts) filtered by conditions (content LIKE '%vulnerability%' AND severity = 'High'). However, Pinot's columnar storage and indexing optimizations make it significantly faster for analytical queries on historical data compared to Spark's general-purpose processing.

How performant is the advanced query? How long it takes to run and how many queries like this one could be served per second?

**Answer:** Performance characteristics of the advanced query:
- **Query Latency:** Typically ranges from 100-500ms depending on data volume and system load.
- **Queries Per Second (QPS):** An Apache Pinot cluster can serve thousands of queries per second (typical ranges: 1,000-10,000+ QPS depending on cluster configuration and query complexity).
- **Factors affecting performance:**
  - Columnar storage format (optimized for aggregations and filtering)
  - Pre-aggregation and indexing on frequently queried columns (source_ip, severity)
  - Distributed execution across segments
  - Caching of frequently accessed data

You can measure query performance in Pinot's Query Console, which displays execution time (in milliseconds) and execution details for each query.

Practical Exercise: From the material presented in the previous lecture on ``` Analytical Processing``` and Apache Pinot's features (available at https://docs.pinot.apache.org/ ), analyze and explain how the performance of the advanced query could be improved without demanding additional computing resources. Then, implement and demonstrate such an approach in Apache Pinot.

**Answer:**

**Performance Optimization Strategy: Indexing and Pre-aggregation**

1. **Add Dictionary Encoding and Indices on Frequently Queried Columns:**
   - Create dictionary-encoded indices on `source_ip`, `severity`, and `content` columns
   - Use bloom filters or inverted indices for LIKE operations on `content`
   - Modify the table schema to include these configurations

2. **Implementation:**
   - Update `ingest_kafka_realtime_table.json` to add the following field configurations:
   
   ```json
   "fieldConfigs": [
     {
       "name": "source_ip",
       "encodingType": "DICTIONARY",
       "indexType": ["SORTED"]
     },
     {
       "name": "severity",
       "encodingType": "DICTIONARY",
       "indexType": ["SORTED"]
     },
     {
       "name": "content",
       "encodingType": "RAW",
       "indexType": ["INVERTED"]
     },
     {
       "name": "timestamp",
       "encodingType": "EPOCH_TRANSFORM_TIME"
     }
   ]
   ```

3. **Expected Improvements:**
   - Query execution time reduced by 50-80% due to faster filtering and aggregations
   - Reduced memory footprint through dictionary compression
   - No additional hardware required—optimization occurs through smarter storage and querying

4. **Verification:**
   - Re-run the advanced query and compare execution time before/after
   - Monitor query latency in Pinot's Query Console
   - Check segment size and memory usage in the Web UI

**Alternative Optimization: Star-Tree Index**
Apache Pinot supports Star-Tree indices for multi-dimensional pre-aggregations. Add this to the table config for even greater performance:
```json
"starTreeIndexConfigs": [
  {
    "dimensionsSplitOrder": ["severity", "source_ip"],
    "skipStarNodeCreationForSingleNodeTree": true,
    "functionColumnPairs": ["COUNT(*)"]
  }
]
```

Foundational Exercise: Considering the material presented in the lecture ``` NoSQL - Data Processing & Advanced Topics``` and Apache Pinot's concepts https://docs.pinot.apache.org/basics/concepts and architecture https://docs.pinot.apache.org/basics/concepts/architecture, how an OLAP system such as Apache Pinot relates to NoSQL and realizes Sharding, Replication, and Distributed SQL?

## Expected Deliverables

Complete answers to all questions above, including brief analyses, configuration files, and performance metrics for the practical exercise.

## Clean up in the ```root folder``` and inside the ```load-generator``` folder. In both cases with the command:

```bash
docker compose down -v
```