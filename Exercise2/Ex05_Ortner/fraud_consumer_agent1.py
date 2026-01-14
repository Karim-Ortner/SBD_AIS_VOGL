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