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

**Answer:** Yes, there are changes in the query results after the load generator starts. The first execution returned no results because the table was empty. After the load generator runs and ingests data via Kafka, the advanced query now returns data showing the source IPs that have the most log entries containing 'vulnerability' with 'High' severity. The query results appear because:
- The load generator continuously produces synthetic log records to Kafka, 
- Pinot's real-time ingestion consumes and indexes these records,
- new data becomes immediately queryable without batch processing delays. 

The result set contains aggregated statistics by source_ip with their match counts.

Moreover, what is the amount of data in the table?

**Answer:** To determine the amount of data in the table, run the query:
```
SELECT COUNT(*) FROM ingest_kafka
```
This returns the total number of records currently in the table. The data volume grows continuously as the load generator produces new records. You can also check the table size via the Pinot Web UI under "Tables" section, which shows metadata including segment count, memory usage, and record count. The exact amount depends on how long the load generator has been running, in our case it is limited to 500000 records.

![alt text](/pictures/image.png)

How this last query relates to the Spark Structured Streaming logs processing example from Exercise 3? 

**Answer:** Both systems perform similar analytical processing on streaming data:
- **Spark Structured Streaming (Exercise 3):** Uses micro-batch processing to compute windowed aggregations on streaming data, typically with micro-batch intervals (e.g., 1-2 seconds).
- **Apache Pinot:** Uses real-time ingestion to insert data into an OLAP data store, enabling immediate querying via SQL.

The key difference is that Spark performs *transformations* and *aggregations* on the stream (computing results as data arrives), while Pinot stores raw events and allows *ad-hoc aggregations* at query time. The advanced query in Pinot is equivalent to computing a streaming aggregation in Spark, both produce grouped statistics (source_ip with counts) filtered by conditions (content LIKE '%vulnerability%' AND severity = 'High'). However, Pinot's columnar storage and indexing optimizations make it significantly faster for analytical queries on historical data compared to Spark's general-purpose processing.

How performant is the advanced query? How long it takes to run and how many queries like this one could be served per second?

**Answer:** Performance characteristics of the advanced query:
- **Query Latency:** Typically ranges from a few milliseconds to a few seconds depending on data volume and system load.
- **Queries Per Second (QPS):** An Apache Pinot cluster can serve thousands of queries per second, depending on cluster configuration and query complexity.
- **Factors affecting performance:**
  - Columnar storage format (optimized for aggregations and filtering)
  - Pre-aggregation and indexing on frequently queried columns (source_ip, severity)
  - Distributed execution across segments
  - Caching of frequently accessed data

I measured query performance in Pinot's Query Console, which displays execution time (in milliseconds) and execution details for each query.

![alt text](/pictures/image1.png)

Practical Exercise: From the material presented in the previous lecture on ``` Analytical Processing``` and Apache Pinot's features (available at https://docs.pinot.apache.org/ ), analyze and explain how the performance of the advanced query could be improved without demanding additional computing resources. Then, implement and demonstrate such an approach in Apache Pinot.

**Answer:**

**Performance Optimization Strategy: Full-Text Search (FTS) Indexing**

The performance optimization implemented uses a **TEXT index on the `content` field** combined with **RAW encoding** to enable efficient full-text search operations. This eliminates the need for expensive LIKE operations that would otherwise require scanning entire segment contents.

1. **Optimization Approach:**
   - Create a Full-Text Search (FTS) index on the `content` column
   - Configure the field with RAW encoding (not dictionary encoded) for text data
   - Use Lucene-based TEXT index for efficient substring and phrase matching
   - Avoid dictionary encoding overhead for large text fields

### Before Optimization (Original Configuration):
![alt text](/pictures/image2.png)

2. **Implementation Details:**

**Schema Configuration (`ingest_kafka_schema_fts.json`):**
```json
{
  "schemaName": "ingest_kafka_fts",
  "dimensionFieldSpecs": [
    { "name": "status", "dataType": "STRING" },
    { "name": "severity", "dataType": "STRING" },
    { "name": "source_ip", "dataType": "STRING" },
    { "name": "user_id", "dataType": "STRING" },
    { "name": "content", "dataType": "STRING" }
  ],
  "dateTimeFieldSpecs": [
    {
      "name": "timestamp",
      "dataType": "LONG",
      "format": "1:MILLISECONDS:EPOCH",
      "granularity": "1:MILLISECONDS"
    }
  ]
}
```

**Table Configuration (`ingest_kafka_realtime_table_fts.json`):**
```json
{
  "tableName": "ingest_kafka_fts",
  "tableType": "REALTIME",
  "segmentsConfig": {
    "timeType": "MILLISECONDS",
    "schemaName": "ingest_kafka_fts",
    "timeColumnName": "timestamp",
    "replicasPerPartition": "1"
  },
  "tenants": {},
  "tableIndexConfig": {
    "loadMode": "MMAP",
    "noDictionaryColumns": ["content"],
    "streamConfigs": {
      "streamType": "kafka",
      "stream.kafka.topic.name": "ingest-kafka",
      "stream.kafka.decoder.class.name": "org.apache.pinot.plugin.inputformat.json.JSONMessageDecoder",
      "stream.kafka.consumer.factory.class.name": "org.apache.pinot.plugin.stream.kafka20.KafkaConsumerFactory",
      "stream.kafka.broker.list": "kafka:9092",
      "realtime.segment.flush.threshold.rows": "0",
      "realtime.segment.flush.threshold.time": "24h",
      "realtime.segment.flush.threshold.segment.size": "50M",
      "stream.kafka.consumer.prop.auto.offset.reset": "smallest"
    }
  },
  "fieldConfigList": [
    {
      "name": "content",
      "encodingType": "RAW",
      "indexTypes": ["TEXT"]
    }
  ],
  "metadata": {
    "customConfigs": {}
  }
}
```

**Key Optimizations:**
- `"noDictionaryColumns": ["content"]` - Prevents expensive dictionary encoding on large text field
- `"encodingType": "RAW"` - Stores content as-is without compression overhead
- `"indexTypes": ["TEXT"]` - Creates Lucene-based full-text search index for efficient LIKE operations

### After Optimization:
![alt text](/pictures/image3.png)

3. **Expected Performance Improvements:**
   - **Query execution time reduction:** only 300 ms and not 3. seconds 
   - **Memory efficiency:** Reduced indexing overhead by avoiding dictionary encoding on large strings
   - **Search capability:** TEXT index provides substring matching at speed comparable to exact match queries
   - **No additional infrastructure:** Optimization achieves through intelligent indexing, not additional hardware


Foundational Exercise: Considering the material presented in the lecture ``` NoSQL - Data Processing & Advanced Topics``` and Apache Pinot's concepts https://docs.pinot.apache.org/basics/concepts and architecture https://docs.pinot.apache.org/basics/concepts/architecture, how an OLAP system such as Apache Pinot relates to NoSQL and realizes Sharding, Replication, and Distributed SQL?

**Answer:**

**1. Apache Pinot as a NoSQL System:**
Apache Pinot is a columnar OLAP database that aligns with NoSQL principles:
- **Schema Flexibility:** While having a defined schema, Pinot allows schema updates without downtime
- **Horizontal Scalability:** Data is distributed across multiple nodes without requiring traditional SQL coordination
- **High Availability:** Supports fault tolerance without relying on traditional ACID properties
- **Real-time Ingestion:** Supports streaming data without batch processing requirements (characteristic of NoSQL systems)

**2. Sharding Implementation:**
- **Segment-based Sharding:** Pinot partitions data into immutable segments, each representing a time window or hash-based partition
- **Table Distribution:** Tables are divided across multiple broker and server nodes
- **Partition Key:** Data is sharded by a partition key (e.g., `source_ip`) to ensure even distribution
- **Query Routing:** The Pinot Broker directs queries to appropriate segments based on partition information
- Benefit: Enables parallel processing of large datasets across distributed infrastructure

**3. Replication Strategy:**
- **Replica Groups:** Each segment is replicated across multiple server nodes within replica groups
- **Fault Tolerance:** If a server fails, replicas on other nodes ensure data availability
- **Lead/Follow Model:** One replica is designated as "lead" (receives updates first), others are followers
- **Zero Data Loss:** Replication factor can be configured (e.g., 2x, 3x replication)
- Benefit: Ensures system availability even with node failures

**4. Distributed SQL Execution:**
- **Scatter-Gather Architecture:** The Broker scatters queries to all relevant segments across servers
- **Parallel Execution:** Each server independently processes its segment locally
- **Result Aggregation:** The Broker aggregates partial results into a final result set
- **Leaf Servers:** Process data locally on segments; minimize data movement across network
- **Distributed Sort/Group By:** Complex aggregations are computed in two phases (leaf and broker level)
- Benefit: Query latency is minimized by avoiding data movement; computation moves to data

**5. NoSQL Characteristics Realized:**
| Aspect | Implementation in Pinot |
|--------|-------------------------|
| **Distributed Architecture** | Data and computation distributed across multiple nodes |
| **Horizontal Scalability** | Add more servers to increase throughput and storage |
| **High Availability** | Segment replication across replica groups |
| **Eventually Consistent** | Real-time segments may lag slightly behind Kafka offsets |
| **Parallel Processing** | Queries execute in parallel across segments and servers |
| **Immutable Records** | Segments are immutable; updates only affect real-time segments |

**6. Practical Example from Our Setup:**
In this exercise:
- **Sharding:** Log records are distributed based on `source_ip` or timestamp across multiple segments
- **Replication:** Each segment exists on multiple broker nodes for redundancy
- **Distributed Query:** The advanced query (filtering by severity and content, grouping by source_ip) is executed in parallel on all relevant segments, then aggregated
- **Real-time:** Kafka provides streaming data that Pinot ingests into real-time segments immediately

**Conclusion:**
Apache Pinot exemplifies a modern distributed OLAP database that combines NoSQL principles (horizontal scalability, fault tolerance) with analytical SQL capabilities. Its architecture achieves performance through data locality, columnar storage, and distributed query execution while maintaining availability through strategic replication and sharding.

## Expected Deliverables

Complete answers to all questions above, including brief analyses, configuration files, and performance metrics for the practical exercise.

## Clean up in the ```root folder``` and inside the ```load-generator``` folder. In both cases with the command:

```bash
docker compose down -v
```