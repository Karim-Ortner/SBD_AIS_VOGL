# Part 1 — Environment Setup and Basics

## 1. Start the environment

Download the repository and start the environment:

```bash
docker compose up -d
```

## 2. Access PostgreSQL

```bash
docker exec -it pg-bigdata psql -U postgres
```

## 3. Load and query data in PostgreSQL

### 3.1 Create a large dataset

```bash
cd data
python3 expand.py
```

Creates `data/people_1M.csv` with ~1 million rows.

```bash
wc -l people_1M.csv
```

### 3.2 Enter PostgreSQL

```bash
docker exec -it pg-bigdata psql -U postgres
```

### 3.3 Create and load the table

```sql
DROP TABLE IF EXISTS people_big;

CREATE TABLE people_big (
  id SERIAL PRIMARY KEY,
  first_name TEXT,
  last_name TEXT,
  gender TEXT,
  department TEXT,
  salary INTEGER,
  country TEXT
);

\COPY people_big(first_name,last_name,gender,department,salary,country)
FROM '/data/people_1M.csv' DELIMITER ',' CSV HEADER;
```

### 3.4 Enable timing

```sql
\timing on
```

## 4. Verification

```sql
SELECT COUNT(*) FROM people_big;
SELECT * FROM people_big LIMIT 10;
```

## 5. Analytical queries

### (a) Simple aggregation

```sql
SELECT department, AVG(salary)
FROM people_big
GROUP BY department
LIMIT 10;
```

### (b) Nested aggregation

```sql
SELECT country, AVG(avg_salary)
FROM (
  SELECT country, department, AVG(salary) AS avg_salary
  FROM people_big
  GROUP BY country, department
) sub
GROUP BY country
LIMIT 10;
```

### (c) Top-N sort

```sql
SELECT *
FROM people_big
ORDER BY salary DESC
LIMIT 10;
```

# Part 2 — Exercises

## Exercise 1 - PostgreSQL Analytical Queries (E-commerce)

In the `ecommerce` folder:

1. Generate a new dataset by running the provided Python script.
```bash
python ./dataset_generator.py
```
- copy it to /data
2. Load the generated data into PostgreSQL in a **new table**.
- go back to postgres by:
```bash
docker exec -it pg-bigdata psql -U postgres
```
- and load the data in a new table with:
```sql
DROP TABLE IF EXISTS orders_big;

CREATE TABLE orders_big (
  id SERIAL PRIMARY KEY,
  order_name TEXT NOT NULL,
  product_category TEXT NOT NULL,
  quantity BIGINT NOT NULL,
  price_per_unit DOUBLE PRECISION NOT NULL,
  order_date DATE NOT NULL,
  country TEXT NOT NULL
);

\COPY orders_big( order_name,
                  product_category,
                  quantity,
                  price_per_unit,
                  order_date,
                  country)
FROM '/data/orders_1M.csv' 
DELIMITER ',' 
CSV HEADER;
```

Using SQL ([see the a list of supported SQL commands](https://www.postgresql.org/docs/current/sql-commands.html)), answer the following questions:

**A.** What is the single item with the highest `price_per_unit`?
```sql
SELECT *
FROM orders_big
ORDER BY price_per_unit DESC
LIMIT 1;
```

   id   | order_name | product_category | quantity | price_per_unit | order_date | country 
--------|------------|------------------|----------|----------------|------------|---------
 841292 | Emma Brown | Automotive       |        3 |           2000 | 2024-10-11 | Italy


**B.** What are the top 3 products category with the highest total quantity sold across all orders?
```sql
SELECT
  product_category,
  SUM(quantity) AS total_quantity
FROM orders_big
GROUP BY product_category
ORDER BY total_quantity DESC
LIMIT 3;
```

 product_category | total_quantity 
------------------|----------------
 Health & Beauty  |         300842
 Electronics      |         300804
 Toys             |         300598



**C.** What is the total revenue per product category?  
(Revenue = `price_per_unit × quantity`)
```sql
SELECT
  product_category,
  SUM(price_per_unit * quantity) AS total_revenue
FROM orders_big
GROUP BY product_category
ORDER BY total_revenue DESC;
```

 product_category |   total_revenue    
------------------|--------------------
 Automotive       |  306589798.8600006
 Electronics      | 241525009.45000046
 Home & Garden    |  78023780.09000012
 Sports           |  61848990.83000008
 Health & Beauty  |  46599817.89000015
 Office Supplies  |  38276061.63999983
 Fashion          | 31566368.220000103
 Toys             | 23271039.020000063
 Grocery          | 15268355.660000034
 Books            | 12731976.040000044


**D.** Which customers have the highest total spending?
```sql
SELECT
  order_name AS customer_name,
  SUM(price_per_unit * quantity) AS total_spent
FROM orders_big
GROUP BY order_name
ORDER BY total_spent DESC
LIMIT 10;
```

 customer_name  |    total_spent    
----------------|-------------------
 Carol Taylor   |         991179.18
 Nina Lopez     | 975444.9499999997
 Daniel Jackson |         959344.48
 Carol Lewis    | 947708.5700000005
 Daniel Young   | 946030.1399999999
 Alice Martinez | 935100.0200000001
 Ethan Perez    | 934841.2400000001
 Leo Lee        | 934796.4799999996
 Eve Young      |         933176.86
 Ivy Rodriguez  | 925742.6400000001


## Exercise 2
Assuming there are naive joins executed by users, such as:
```sql
SELECT COUNT(*)
FROM people_big p1
JOIN people_big p2
  ON p1.country = p2.country;
```
## Problem Statement

This query takes more than **10 minutes** to complete, significantly slowing down the entire system. Additionally, the **OLTP database** currently in use has inherent limitations in terms of **scalability and efficiency**, especially when operating in **large-scale cloud environments**.

## Discussion Question

Considering the requirements for **scalability** and **efficiency**, what **approaches and/or optimizations** can be applied to improve the system’s:

- Scalability  
- Performance  
- Overall efficiency  

Please **elaborate with a technical discussion**.

### option 1:
#### Query & Schema Optimization
```sql
SELECT SUM(cnt * cnt)
FROM (
  SELECT COUNT(*) AS cnt
  FROM people_big
  GROUP BY country
) x;
```
- Eliminates expensive N-to-N join.
- Reduces billions of rows to a single grouped table.
- Add an index on join columns:
```sql
CREATE INDEX idx_country ON people_big(country);
```
- Speeds up joins and aggregations on country.
- Materialized summary tables:
  - Precompute counts per country.
  - Serve repeated queries without scanning the full table.

### option 2:
#### Move Analytical Workloads Off OLTP
- Use an OLAP / columnar system (like Snowflake) for heavy joins and aggregations.
- Benefits:
  - Parallel processing across multiple nodes.
  - Columnar storage reduces I/O.
  - Handles large-scale datasets efficiently.
- Maintain OLTP for transactional workloads only to avoid slowing down the system.


> **Optional:** Demonstrate your proposed solution in practice (e.g., architecture diagrams, SQL examples, or code snippets).


## Exercise 3
## Run with Spark (inside Jupyter)

Open your **Jupyter Notebook** environment:

- **URL:** http://localhost:8888/?token=lab  
- **Action:** Create a new notebook

Then run the following **updated Spark example**, which uses the same data stored in **PostgreSQL**.

---

## Spark Example Code

```python
# ============================================
# 0. Imports & Spark session
# ============================================

import time
import builtins  # <-- IMPORTANT
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    avg,
    round as spark_round,   # Spark round ONLY for Columns
    count,
    col,
    sum as _sum
)

spark = (
    SparkSession.builder
    .appName("PostgresVsSparkBenchmark")
    .config("spark.jars.packages", "org.postgresql:postgresql:42.7.2")
    .config("spark.eventLog.enabled", "true")
    .config("spark.eventLog.dir", "/tmp/spark-events")
    .config("spark.history.fs.logDirectory", "/tmp/spark-events")
    .config("spark.sql.shuffle.partitions", "4")
    .config("spark.default.parallelism", "4")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

# ============================================
# 1. JDBC connection config
# ============================================

jdbc_url = "jdbc:postgresql://postgres:5432/postgres"
jdbc_props = {
    "user": "postgres",
    "password": "postgres",
    "driver": "org.postgresql.Driver"
}

# ============================================
# 2. Load data from PostgreSQL
# ============================================

print("\n=== Loading people_big from PostgreSQL ===")

start = time.time()

df_big = spark.read.jdbc(
    url=jdbc_url,
    table="people_big",
    properties=jdbc_props
)

# Force materialization
row_count = df_big.count()

print(f"Rows loaded: {row_count}")
print("Load time:", builtins.round(time.time() - start, 2), "seconds")

# Register temp view
df_big.createOrReplaceTempView("people_big")

# ============================================
# 3. Query (a): Simple aggregation
# ============================================

print("\n=== Query (a): AVG salary per department ===")

start = time.time()

q_a = (
    df_big
    .groupBy("department")
    .agg(spark_round(avg("salary"), 2).alias("avg_salary"))
    .orderBy("department", ascending=False)
    .limit(10)
)

q_a.collect()
q_a.show(truncate=False)
print("Query (a) time:", builtins.round(time.time() - start, 2), "seconds")

# ============================================
# 4. Query (b): Nested aggregation
# ============================================

print("\n=== Query (b): Nested aggregation ===")

start = time.time()

q_b = spark.sql("""
SELECT country, AVG(avg_salary) AS avg_salary
FROM (
    SELECT country, department, AVG(salary) AS avg_salary
    FROM people_big
    GROUP BY country, department
) sub
GROUP BY country
ORDER BY avg_salary DESC
LIMIT 10
""")

q_b.collect()
q_b.show(truncate=False)
print("Query (b) time:", builtins.round(time.time() - start, 2), "seconds")

# ============================================
# 5. Query (c): Sorting + Top-N
# ============================================

print("\n=== Query (c): Top 10 salaries ===")

start = time.time()

q_c = (
    df_big
    .orderBy(col("salary").desc())
    .limit(10)
)

q_c.collect()
q_c.show(truncate=False)
print("Query (c) time:", builtins.round(time.time() - start, 2), "seconds")

# ============================================
# 6. Query (d): Heavy self-join (COUNT only)
# ============================================

print("\n=== Query (d): Heavy self-join COUNT (DANGEROUS) ===")

start = time.time()

q_d = (
    df_big.alias("p1")
    .join(df_big.alias("p2"), on="country")
    .count()
)

print("Join count:", q_d)
print("Query (d) time:", builtins.round(time.time() - start, 2), "seconds")

# ============================================
# 7. Query (d-safe): Join-equivalent rewrite
# ============================================

print("\n=== Query (d-safe): Join-equivalent rewrite ===")

start = time.time()

grouped = df_big.groupBy("country").agg(count("*").alias("cnt"))

q_d_safe = grouped.select(
    _sum(col("cnt") * col("cnt")).alias("total_pairs")
)

q_d_safe.collect()
q_d_safe.show()
print("Query (d-safe) time:", builtins.round(time.time() - start, 2), "seconds")

# ============================================
# 8. Cleanup
# ============================================

spark.stop()
```
## Analysis and Discussion

Now, explain in your own words:

### 1. What the Spark code does:
Describe the workflow, data loading, and the types of queries executed (aggregations, sorting, self-joins, etc.).

Loads 1M rows from PostgreSQL into distributed memory, then runs 5 queries: simple aggregation, nested aggregation, top-N sorting, self-join (expensive), and join rewrite (optimized). Each operation is timed.

### 2. Architectural contrasts with PostgreSQL

Compare the Spark distributed architecture versus PostgreSQL's single-node capabilities, including scalability, parallelism, and data processing models.

| | PostgreSQL | Spark |
|---|-----------|-------|
| **Processing** | Single server, sequential | Distributed cluster, parallel |
| **Scalability** | Vertical (bigger hardware) | Horizontal (add nodes) |
| **Memory** | Single machine limit | Distributed across cluster |
| **I/O** | Local disk | Network shuffles |

### 3. Advantages and limitations

Highlight the benefits of using Spark for large-scale data processing (e.g., in-memory computation, distributed processing) and its potential drawbacks (e.g., setup complexity, overhead for small datasets).

**Advantages:** Handles TB/PB scale, in-memory processing, fault tolerant, lazy optimization, elastic scaling

**Limitations:** Complex setup, overhead for small datasets, no ACID transactions, memory pressure on shuffles, network bottlenecks

### 4. Relation to Exercise 2

Connect this approach to the concepts explored in Exercise 2, such as performance optimization and scalability considerations.

Exercise 2 optimized queries within PostgreSQL (rewrites, indexes). Exercise 3 applies the same optimization (query d-safe rewrite) on distributed infrastructure. Combined: algorithmic optimization + distributed execution solves scalability limits single-node cannot overcome.

## Exercise 4
Port the SQL queries from exercise 1 to spark.

```python
# ============================================
# 0. Imports & Spark session
# ============================================

import time
import builtins  # <-- IMPORTANT
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    avg,
    round as spark_round,   # Spark round ONLY for Columns
    count,
    col,
    sum as _sum
)

spark = (
    SparkSession.builder
    .appName("PostgresVsSparkBenchmark")
    .config("spark.jars.packages", "org.postgresql:postgresql:42.7.2")
    .config("spark.eventLog.enabled", "true")
    .config("spark.eventLog.dir", "/tmp/spark-events")
    .config("spark.history.fs.logDirectory", "/tmp/spark-events")
    .config("spark.sql.shuffle.partitions", "4")
    .config("spark.default.parallelism", "4")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")
```

```python
# ============================================
# 1. JDBC connection config
# ============================================

jdbc_url = "jdbc:postgresql://postgres:5432/postgres"
jdbc_props = {
    "user": "postgres",
    "password": "postgres",
    "driver": "org.postgresql.Driver"
}
```

```python
# ============================================
# 2. Load data from PostgreSQL
# ============================================

print("\n=== Loading orders_big from PostgreSQL ===")

start = time.time()

df_big = spark.read.jdbc(
    url=jdbc_url,
    table="orders_big",
    properties=jdbc_props
)

# Force materialization
row_count = df_big.count()

print(f"Rows loaded: {row_count}")
print("Load time:", builtins.round(time.time() - start, 2), "seconds")

# Register temp view
df_big.createOrReplaceTempView("orders_big")
```

```
=== Loading orders_big from PostgreSQL ===
Rows loaded: 1000000
Load time: 3.22 seconds
```

```python
q_a = spark.sql("""
SELECT *
FROM orders_big
ORDER BY price_per_unit DESC
LIMIT 1;
""")

q_a.collect()
```

```
[Row(id=841292, order_name='Emma Brown', product_category='Automotive', quantity=3, price_per_unit=2000.0, order_date=datetime.date(2024, 10, 11), country='Italy')]
```

```python
q_b = spark.sql("""
SELECT
  product_category,
  SUM(quantity) AS total_quantity
FROM orders_big
GROUP BY product_category
ORDER BY total_quantity DESC
LIMIT 3;
""")

q_b.collect()
```

```
[Row(product_category='Health & Beauty', total_quantity=300842),
 Row(product_category='Electronics', total_quantity=300804),
 Row(product_category='Toys', total_quantity=300598)]
```

```python
q_c = spark.sql("""
SELECT
  product_category,
  SUM(price_per_unit * quantity) AS total_revenue
FROM orders_big
GROUP BY product_category
ORDER BY total_revenue DESC;
""")

q_c.collect()
```

```
[Row(product_category='Automotive', total_revenue=306589798.8599943),
 Row(product_category='Electronics', total_revenue=241525009.45000267),
 Row(product_category='Home & Garden', total_revenue=78023780.0900001),
 Row(product_category='Sports', total_revenue=61848990.830000326),
 Row(product_category='Health & Beauty', total_revenue=46599817.8900003),
 Row(product_category='Office Supplies', total_revenue=38276061.640000574),
 Row(product_category='Fashion', total_revenue=31566368.219999947),
 Row(product_category='Toys', total_revenue=23271039.019999716),
 Row(product_category='Grocery', total_revenue=15268355.660000028),
 Row(product_category='Books', total_revenue=12731976.03999989)]
```

```python
q_d = spark.sql("""
SELECT
  order_name AS customer_name,
  SUM(price_per_unit * quantity) AS total_spent
FROM orders_big
GROUP BY order_name
ORDER BY total_spent DESC
LIMIT 10;
""")

q_d.collect()
```

```
[Row(customer_name='Carol Taylor', total_spent=991179.1800000003),
 Row(customer_name='Nina Lopez', total_spent=975444.9499999998),
 Row(customer_name='Daniel Jackson', total_spent=959344.4800000001),
 Row(customer_name='Carol Lewis', total_spent=947708.5700000002),
 Row(customer_name='Daniel Young', total_spent=946030.1400000004),
 Row(customer_name='Alice Martinez', total_spent=935100.0199999999),
 Row(customer_name='Ethan Perez', total_spent=934841.2399999991),
 Row(customer_name='Leo Lee', total_spent=934796.4799999993),
 Row(customer_name='Eve Young', total_spent=933176.8599999989),
 Row(customer_name='Ivy Rodriguez', total_spent=925742.6400000005)]
```

## Clean up
```bash
docker compose down
```