from kafka import KafkaConsumer
import json

print("Starting Kafka Consumer...")
print("Listening to 'user-events' topic on localhost:9092...")

# Set up the consumer
consumer = KafkaConsumer(
    'user-events',
    bootstrap_servers=['localhost:9092'],
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest'
)

for message in consumer:
    event = message.value
    print(f"*** Received Event ***")
    print(f"User: {event.get('username')} [{event.get('role', 'user')}]")
    print(f"Action: {event.get('action')}")
    print(f"Status: {event.get('status')}")
    print("-" * 20)
