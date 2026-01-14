# Part 1 — Environment Setup and Basics

## 1. Start the environment

Download the repository and start the environment:

```bash
docker compose up -d
```

Check if the **four containers** are running:
- postgres
- kafka
- kafka-ui
- connect

## 2. Access PostgreSQL

```bash
docker exec -it postgres psql -U postgres
```


# Kafka Quick Start (Docker)

## A. Check Kafka is running
```bash
docker ps
```
**Explanation**  
Confirms that the Kafka broker container is running and shows its container name (e.g. `kafka`).

---

## B. Create a topic with multiple partitions
```bash
docker exec -it kafka kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create \
  --topic activity.streaming \
  --partitions 4 \
  --replication-factor 1
```
**Explanation**
- `--topic`: Name of the Kafka topic  
- `--partitions 4`: Creates three partitions to allow parallelism  
- `--replication-factor 1`: One replica per partition (suitable for local development)

---

## C. List all topics
```bash
docker exec -it kafka kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --list
```
**Explanation**  
Displays all topics currently available in the Kafka cluster.

---

## D. Describe a topic
```bash
docker exec -it kafka kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --topic activity.streaming
```
**Explanation**  
Shows partition count, leaders, replicas, and in-sync replicas (ISR).

---

## E. List topic configuration
```bash
docker exec -it kafka kafka-configs.sh \
  --bootstrap-server localhost:9092 \
  --entity-type topics \
  --entity-name activity.streaming \
  --describe
```
**Explanation**  
Displays topic-level configurations such as retention and cleanup policies.  
Configurations not listed inherit Kafka broker defaults.

---

## F. Produce messages to the topic

### F.1 Basic producer
```bash
docker exec -it kafka kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic activity.streaming
```

Example input:
```text
{"id":1,"name":"Alice"}
{"id":2,"name":"Bob"}
```

**Explanation**  
Messages are distributed across partitions in a round-robin fashion when no key is provided.

---

### F.2 Producer with keys
```bash
docker exec -it kafka kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic activity.streaming \
  --property parse.key=true \
  --property key.separator=:
```

Example input:
```text
1:{"id":1,"name":"Alice"}
1:{"id":1,"name":"Alice-updated"}
2:{"id":2,"name":"Bob"}
```

**Explanation**  
Messages with the same key are routed to the same partition, preserving per-key ordering.

---

## G. Consume messages from the topic

### G.1 Consume from the beginning
```bash
docker exec -it kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic activity.streaming \
  --from-beginning
```

**Explanation**  
Reads all messages from the beginning of the topic.

---

### G.2 Consume using a consumer group
```bash
docker exec -it kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic activity.streaming \
  --group customers-service
```

**Explanation**  
Consumers in the same group share partitions and automatically commit offsets.

---

## H. Inspect consumer group status
```bash
docker exec -it kafka kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --group customers-service
```

**Explanation**  
Shows partition assignments, current offsets, and consumer lag.

---

## I. Delete the topic (optional)
```bash
docker exec -it kafka kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --delete \
  --topic activity.streaming
```

**Explanation**  
Deletes the topic and all stored data (requires `delete.topic.enable=true` on the broker).



# Debezium CDC with PostgreSQL and Kafka


## Verify the services
- Kafka UI: http://localhost:8080  
- Connector plugins endpoint: http://localhost:8083/connector-plugins  

Ensure that the Connect service responds successfully.

## Example: Insert a row in PostgreSQL

### Create a new database
```sql
CREATE DATABASE activity;
```

### Connect to the new database
```sql
\c activity
```

### Create the table
```sql
CREATE TABLE activity (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255)
);
```

## Register the Debezium Connector

The Docker Compose file only starts the Kafka Connect engine.  
You must explicitly register a Debezium connector so it starts watching PostgreSQL.

In **another terminal**, run:

```bash
curl -i -X POST   -H "Accept:application/json"   -H "Content-Type:application/json"   localhost:8083/connectors/   -d '{
    "name": "activity-connector",
    "config": {
      "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
      "tasks.max": "1",
      "database.hostname": "postgres",
      "database.port": "5432",
      "database.user": "postgres",
      "database.password": "postgrespw",
      "database.dbname": "activity",
      "slot.name": "activityslot",
      "topic.prefix": "dbserver1",
      "plugin.name": "pgoutput",
      "database.replication.slot.name": "debeziumactivity"
    }
  }'
```

### Check Debezium status
The connector and its tasks should be in the `RUNNING` state:

```bash
curl -s http://localhost:8083/connectors/activity-connector/status
```

Ouput:
```bash
{"name":"activity-connector","connector":{"state":"RUNNING","worker_id":"172.22.0.4:8083"},"tasks":[{"id":0,"state":"RUNNING","worker_id":"172.22.0.4:8083"}],"type":"source"}
```

## Insert a record into PostgreSQL

Back in the PostgreSQL console, insert a record:

```sql
INSERT INTO activity(id, name) VALUES (1, 'Alice');
```

## Consume from the Kafka topic

```bash
docker exec -it kafka kafka-console-consumer.sh   --bootstrap-server localhost:9092   --topic dbserver1.public.activity  --from-beginning
```

In the Kafka UI (http://localhost:8080), verify that new topics appear.

Debezium will produce a Kafka message on the topic:

```
dbserver1.public.activity
```

With a payload similar to:

```json
{
  "op": "c",
  "after": {
    "id": 1,
    "name": "Alice"
  }
}
```

# Activity 1
Considering the above part ```Debezium CDC with PostgreSQL and Kafka```, explain with your own words what it does and why it is a relevant software architecture for Big Data in the AI era and for which use cases.

Explanation:
> Debezium tails PostgreSQL’s WAL (Write-Ahead Log) and turns every insert/update/delete into Kafka events, so I get a real-time stream of database changes without triggers or heavy polling. Kafka gives me a durable, replayable log that many consumers can read independently, which decouples my OLTP database from analytics and downstream systems. This is ideal for AI/Big Data because fresh data flows continuously to feature stores, models, and dashboards while keeping the transactional DB fast. Typical wins are fraud detection, search/cache sync, and continuous lake/warehouse ingest.

# Activity 2
## Scenario:
You run a temperature logging system in a small office. Sensors report the temperature once per minute and write the sensor readings into a PostgreSQL table

## Running instructions
It is recommended to run the scripts (e.g., ```temperature_data_producer.py``` file) in a Python virtual environments venv, basic commands from the ```activity.streaming``` folder:
```bash
python3 -m venv venv
source venv/Scripts/activate 
pip install --upgrade pip
pip install -r requirements.txt
```
Then one can run the python scripts.

## Characteristics:

Low volume (~1 row per minute)

Single consumer (reporting script)

No real-time streaming needed

## Part 1
In a simple use case where sensor readings need to be processed every 10 minutes to calculate the average temperature over that time window, describe which software architecture would be most appropriate for fetching the data from PostgreSQL, and explain the rationale behind your choice.

Explanation:
> For this use case, I’d use a scheduled batch job that queries PostgreSQL directly every 10 minutes, computes the average (in SQL with AVG() or in Python after fetching), and stores or prints the result. The volume is tiny and there’s only one consumer, so direct DB polling is the simplest, most reliable option—no need for Kafka or streaming. Make sure the readings table has a timestamp column indexed, so filtering “last 10 minutes” is fast, and run the job via cron/Task Scheduler (or a small Python loop with sleep).

## Part 2
From the architectural choice made in ```Part 1```, implement the solution to consume and processing the data generated by the ```temperature_data_producer.py``` file (revise its features!). The basic logic from the file ```temperature_data_consumer.py``` should be extended with the conection to data source defined in ```Part 1```'s architecture..

```bash
$ python ./temperature_data_producer.py
```

Output:

```bash
Table ready.
2026-01-07 19:26:01.807118 - Inserted temperature: 21.25 °C
2026-01-07 19:27:01.813139 - Inserted temperature: 24.75 °C
2026-01-07 19:28:01.821115 - Inserted temperature: 23.91 °C
```

--------------------------

python file:
- temperature_data_consumer.py

```python
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
import psycopg2
from psycopg2 import sql

DB_NAME = os.getenv("OFFICE_DB", "office_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgrespw")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
SENSOR_ID = os.getenv("SENSOR_ID")  # optional: filter by specific sensor

def get_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )

# -------------------------
# Periodically compute average over last 10 minutes
# -------------------------
conn = None
try:
    conn = get_connection()
    while True:
        ten_minutes_ago = datetime.now() - timedelta(minutes=10)
        with conn.cursor() as cur:
            if SENSOR_ID:
                cur.execute(
                    """
                    SELECT AVG(temperature)
                    FROM temperature_readings
                    WHERE sensor_id = %s AND recorded_at >= %s
                    """,
                    (SENSOR_ID, ten_minutes_ago),
                )
            else:
                cur.execute(
                    """
                    SELECT AVG(temperature)
                    FROM temperature_readings
                    WHERE recorded_at >= %s
                    """,
                    (ten_minutes_ago,),
                )
            row = cur.fetchone()
            avg_temp = row[0] if row else None
        if avg_temp is not None:
            print(f"{datetime.now()} - Average temperature last 10 minutes: {avg_temp:.2f} °C")
        else:
            print(f"{datetime.now()} - No data in last 10 minutes.")
        time.sleep(600)  # every 10 minutes
except KeyboardInterrupt:
    print("Stopped consuming data.")
except Exception as e:
    print(f"Error while consuming data: {e}")
finally:
    try:
        if conn:
            conn.close()
    except Exception:
        pass
    print("Exiting.")
```

Run the temperature data consumer:

```bash
python temperature_data_consumer.py
```

Ouput:
```bash
2026-01-07 19:29:13.920210 - Average temperature last 10 minutes: 24.29 °C
```

## Part 3
Discuss the proposed architecture in terms of resource efficiency, operability, and deployment complexity. This includes analyzing how well the system utilizes compute, memory, and storage resources; how easily it can be operated, monitored, and debugged in production.

Resource efficiency: 
- The scheduled query uses very little CPU/memory and runs only once every 10 minutes. With an index on the timestamp column, the DB reads are fast and light; no extra storage or streaming cluster is needed.

Operability: 
- It’s simple to run and monitor—a small script plus Postgres. You can schedule it with Task Scheduler/cron, add basic logging, and alert on errors or empty results.

Deployment complexity:
- Very low. It’s just a Python script and a database connection (optionally in a container); no Kafka/Connect, no brokers, and no complex pipelines to manage.

# Activity 3
## Scenario:
A robust fraud detection system operating at high scale must be designed to handle extremely high data ingestion rates while enabling near real-time analysis by multiple independent consumers. In this scenario, potentially hundreds of thousands of transactional records per second are continuously written into an OLTP PostgreSQL database (see an example simulating it with a data generator inside the folder ```Activity3```), which serves as the system of record and guarantees strong consistency, durability, and transactional integrity. Moreover, the records generated are needed by many consumers in near real-time (see inside the folder ```Activity3``` two examples simulating agents consuming the records and generating alerts).  Alerts or enriched events generated by these agents can then be forwarded to downstream systems, such as alerting services, dashboards, or case management tools.

## Running instructions
It is recommended to run the scripts in a Python virtual environments venv, basic commands from the ```Activity3``` folder:
```bash
python3 -m venv venv
source venv/Scripts/activate 
pip install --upgrade pip
pip install -r requirements.txt
```
Then one can run the python scripts.

> using same venv as above Activity 2 is possible, just ensure all required packages are installed.

## Characteristics:

High data volume (potentially hundreds of thousands of records per second)

Multiple consumer agents

Near real-time streaming needed

## Part 1

Describe which software architecture would be most appropriate for fetching the data from PostgreSQL and generate alerts in real-time. Explain the rationale behind your choice.

Explanation:
> Use Debezium CDC to stream changes from Postgres into Kafka, then let each fraud agent read the same Kafka topic. Partition events by something like user_id so processing scales horizontally while keeping per-user order. This avoids hammering the database, delivers near real-time data to many consumers, and lets you replay or scale independently as load grows

## Part 2
From the architectural choice made in ```Part 1```, implement the 'consumer' to fetch and process the records generated by the ```fraud_data_producer.py``` file (revise its features!). The basic logic from the files ```fraud_consumer_agent1.py.py``` and ```fraud_consumer_agent2.py.py``` should be extended with the conection to data source defined in ```Part 1```'s architecture.

```bash
$ python ./fraud_data_producer.py
```
Output:
```bash
Inserted 1000 transactions...
Inserted 1000 transactions...
Inserted 1000 transactions...
Inserted 1000 transactions...
Inserted 1000 transactions...
Inserted 1000 transactions...
Inserted 1000 transactions...
...
```

Setup connector:
```bash
curl -i -X POST \
  -H "Accept:application/json" \
  -H "Content-Type:application/json" \
  localhost:8083/connectors/ \
  -d '{
    "name": "fraud-detection-connector",
    "config": {
      "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
      "tasks.max": "1",
      "database.hostname": "postgres",
      "database.port": "5432",
      "database.user": "postgres",
      "database.password": "postgrespw",
      "database.dbname": "mydb",
      "slot.name": "fraudslot",
      "topic.prefix": "fraud-detection",
      "plugin.name": "pgoutput",
      "database.replication.slot.name": "debeziumfraud",
      "table.include.list": "public.transactions"
    }
  }'
  ```
--------------------------

changes to python files:

- fraud_consumer_agent1.py
```python
# This agent calculates a running average for each user and flags transactions that are significantly higher than their usual behavior (e.g., $3\sigma$ outliers).

# change: I added Kafka consumer wiring + decimal decoder for Debezium
import json
import statistics
import base64
from kafka import KafkaConsumer

# Configuration (simple and local by default)
KAFKA_BOOTSTRAP_SERVERS = ['localhost:9094']  # change: new config for broker
KAFKA_TOPIC = 'fraud-detection.public.transactions'  # change: Debezium topic name
CONSUMER_GROUP = 'fraud-detection-agent1'  # change: consumer group for this agent

# In-memory store for user spending patterns
user_spending_profiles = {}

def decode_decimal(encoded_bytes):
    """Decode Debezium DECIMAL bytes to float (scale=2)."""
    # change: added to handle Debezium's base64 DECIMAL
    if isinstance(encoded_bytes, str):
        try:
            raw = base64.b64decode(encoded_bytes)
            value = int.from_bytes(raw, byteorder='big', signed=True)
            return float(value) / 100
        except Exception:
            return None
    elif isinstance(encoded_bytes, (int, float)):
        return float(encoded_bytes)
    return None

def analyze_pattern(data):
    user_id = data['user_id']
    amount = decode_decimal(data['amount'])  # change: use decoder instead of float()
    if amount is None:
        return False

    if user_id not in user_spending_profiles:
        user_spending_profiles[user_id] = []

    history = user_spending_profiles[user_id]

    # Analyze if transaction is an outlier (Need at least 3 transactions to judge)
    is_anomaly = False
    if len(history) >= 3:
        avg = statistics.mean(history)
        stdev = statistics.stdev(history) if len(history) > 1 else 0

        # If amount is > 3x the average (Simple heuristic)
        if amount > (avg * 3) and amount > 500:
            is_anomaly = True

    # Update profile
    history.append(amount)
    # Keep only last 50 transactions per user for memory efficiency
    if len(history) > 50:
        history.pop(0)

    return is_anomaly

print("🧬 Anomaly Detection Agent started…")

# change: create a Kafka consumer hooked to Debezium topic
consumer = KafkaConsumer(
    KAFKA_TOPIC,
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    group_id=CONSUMER_GROUP,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',
    enable_auto_commit=True,
)

for message in consumer:
    payload = message.value.get('payload', {})
    data = payload.get('after')

    if data:
        is_fraudulent_pattern = analyze_pattern(data)
        if is_fraudulent_pattern:
            print(
                f"🚨 ANOMALY DETECTED: User {data['user_id']} spent ${decode_decimal(data['amount'])} (significantly higher than average)"
            )
        else:
            print(f"📊 Profile updated for User {data['user_id']}")
```

- fraud_consumer_agent2.py
```python
#This agent uses a sliding window (simulated) to perform velocity checks and score the transaction

# change: I wired this agent to Kafka (Debezium topic) and added decimal decoding
import json
from collections import deque
import time
import base64
from kafka import KafkaConsumer

# Configuration
KAFKA_BOOTSTRAP_SERVERS = ['localhost:9094']  # change: broker config
KAFKA_TOPIC = 'fraud-detection.public.transactions'  # change: Debezium topic
CONSUMER_GROUP = 'fraud-detection-agent2'  # change: consumer group

# Simulated In-Memory State for Velocity Checks.
user_history = {}

def decode_decimal(encoded_bytes):
    """Decode Debezium DECIMAL bytes to float (scale=2)."""
    # change: added to handle DECIMAL coming as base64
    if isinstance(encoded_bytes, str):
        try:
            decoded = base64.b64decode(encoded_bytes)
            value = int.from_bytes(decoded, byteorder='big', signed=True)
            return float(value) / 100
        except Exception:
            return None
    elif isinstance(encoded_bytes, (int, float)):
        return float(encoded_bytes)
    return None

def analyze_fraud(transaction):
    user_id = transaction['user_id']
    amount = decode_decimal(transaction['amount'])  # change: use decoder
    if amount is None:
        return 0

    # 1. Velocity Check (Recent transaction count)
    now = time.time()
    if user_id not in user_history:
        user_history[user_id] = deque()

    # Keep only last 60 seconds of history
    user_history[user_id].append(now)
    while user_history[user_id] and user_history[user_id][0] < now - 60:
        user_history[user_id].popleft()

    velocity = len(user_history[user_id])

    # 2. Heuristic Fraud Scoring
    score = 0
    if velocity > 5:
        score += 40  # Too many transactions in a minute
    if amount > 4000:
        score += 50  # High value transaction

    # 3. Simulate ML Model Hand-off
    # model.predict([[velocity, amount]])

    return score

# change: create a Kafka consumer for CDC events
consumer = KafkaConsumer(
    KAFKA_TOPIC,
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    group_id=CONSUMER_GROUP,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',  # start reading from the beginning
    enable_auto_commit=True
)

print("Agent 2 started. Listening for CDC events…")
for message in consumer:
    # Debezium wraps data in an 'after' block
    payload = message.value.get('payload', {})
    data = payload.get('after')

    if data:
        fraud_score = analyze_fraud(data)
        if fraud_score > 70:
            print(
                f"⚠️ HIGH FRAUD ALERT: User {data['user_id']} | Score: {fraud_score} | Amt: {decode_decimal(data['amount'])}"
            )
        else:
            print(f"✅ Transaction OK: {data['id']} (Score: {fraud_score})")
```

Run the two fraud detection agents:

```bash
python fraud_consumer_agent1.py
```
Output:
```bash
📊 Profile updated for User 1277
📊 Profile updated for User 2546
📊 Profile updated for User 1140
📊 Profile updated for User 8077
🚨 ANOMALY DETECTED: User 3214 spent $4398.48 (significantly higher than average)
📊 Profile updated for User 3032
📊 Profile updated for User 4003
📊 Profile updated for User 8828
📊 Profile updated for User 4148
```

```bash
python fraud_consumer_agent2.py
```
Output:
```bash
✅ Transaction OK: 14254 (Score: 0)
✅ Transaction OK: 14255 (Score: 0)
✅ Transaction OK: 14256 (Score: 50)
✅ Transaction OK: 14257 (Score: 50)
✅ Transaction OK: 14258 (Score: 50)
⚠️ HIGH FRAUD ALERT: User 1099 | Score: 90 | Amt: 4734.85
✅ Transaction OK: 14260 (Score: 0)
✅ Transaction OK: 14261 (Score: 0)
✅ Transaction OK: 14262 (Score: 50)
```

## Part 3
Discuss the proposed architecture in terms of resource efficiency, operability, maintainability, deployment complexity, and overall performance and scalability. This includes discussing how well the system utilizes compute, memory, and storage resources; how easily it can be operated, monitored, and debugged in production; how maintainable and evolvable the individual components are over time; the effort required to deploy and manage the infrastructure; and the system’s ability to sustain increasing data volumes, higher ingestion rates, and a growing number of fraud detection agents without degradation of latency or reliability.


Resource Efficiency

- Compute: Moderate always-on CPU for Kafka/Connect/agents; OLTP protected from polling load.
- Memory/Storage: Small per-agent state; Kafka logs consume disk but enable replay.

Operability

- Monitoring: Kafka UI and Connect REST cover brokers/connectors; add simple agent logs/metrics.
- Debugging/Recovery: Multi-hop path needs end-to-end checks; offsets enable quick replays and restarts.

Maintainability

- Modularity: Small, decoupled agents are easy to evolve or add without coordination.
- Contracts: Versioned event schemas prevent consumer breakage; config is declarative and reproducible.

Deployment Complexity

- Stack: Requires Postgres, Kafka, Connect (Debezium), plus agents; scripted setup recommended.
- Scaling Ops: Partition/topics and consumer groups scale horizontally; infra-as-code simplifies rollout.

Performance & Scalability

- Latency/Throughput: Near real-time with high sustained rates; partition by user_id for ordered parallelism.
- Growth: Add partitions/agents as volume and consumers increase without impacting OLTP.

## Part 4
Compare the proposed architecture to Exercise 3 from previous lecture where the data from PostgreSQL was loaded to Spark (as a consumer) using the JDBC connector. Discuss both approaches at least in terms of performance, resource efficiency, and deployment complexity. 

Performance

Latency: CDC + Kafka delivers near real-time (ms–s); Spark JDBC is batch (seconds–minutes) unless you add complex micro-batch logic.
Throughput: Kafka sustains very high ingest; Spark JDBC is limited by DB connections, query intervals, and result materialization.
DB impact: CDC reads WAL with minimal OLTP overhead; JDBC polling runs SELECTs that add read load and contention.
Resource Efficiency

Compute: CDC + Kafka runs continuously (broker, Connect, agents) but offloads work from Postgres; Spark needs JVM executors and driver plus recurring query compute.
Memory: Kafka brokers buffer messages; agents hold small state. Spark jobs cache/shuffle data and can be memory-heavy.
Storage: Kafka topic logs consume disk but enable replay; Spark often writes intermediates/checkpoints to storage.
Deployment Complexity

CDC + Kafka: Requires Postgres, Kafka, Kafka Connect (Debezium), and agents; connector registration and topic/partition management.
Spark JDBC: Requires Postgres and a Spark stack (driver + executors/cluster); JDBC configs, scheduling, and cluster management.
Operations: CDC has offsets, replay, and decoupled consumers; Spark has DAGs, checkpoints, and cluster tuning.
When to Use Which

CDC + Kafka: Real-time alerts, many independent consumers, high-volume streams, replayability, strict OLTP isolation.
Spark JDBC: Periodic/batch analytics, heavy SQL/ML transformations, data lake writes, lower-frequency processing.

# Submission
Send the exercises' resolution on Moodle and be ready to shortly present your solutions (5-8 minutes) in the next Exercise section (14.01.2026).
