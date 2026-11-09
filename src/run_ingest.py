import json
import uuid

from fintech_ingest import InfraiClient, InfraiError, PaymentEvent, ingest_event


def main() -> None:
    event = PaymentEvent("evt_1001", "acct_42", 1840.50, "USD", "new beneficiary transfer", 0.82)
    client = InfraiClient()
    collection = f"fintech-demo-{uuid.uuid4().hex}"
    try:
        result = ingest_event(client, event, collection=collection)
    finally:
        try:
            client.delete_collection(collection)
        except InfraiError as exc:
            # Embedding or creation may have failed before the collection existed.
            if exc.status != 404:
                raise
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
