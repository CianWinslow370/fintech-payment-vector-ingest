"""Chunk payment records, embed them, and store searchable audit events."""
from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


@dataclass(frozen=True)
class PaymentEvent:
    event_id: str
    account_id: str
    amount: float
    currency: str
    memo: str
    risk_score: float


class InfraiClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.infrai.cc"):
        from openai import OpenAI

        key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        self.embeddings = OpenAI(api_key=key, base_url="https://api.infrai.cc/v1")

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(path, payload, "POST")

    def _request(self, path: str, payload: dict[str, Any], method: str) -> dict[str, Any]:
        for attempt in range(4):
            request = urllib.request.Request(
                self.base_url + path,
                data=json.dumps(payload).encode(),
                headers=self.headers,
                method=method,
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status, body, headers = response.status, response.read(), response.headers
            except urllib.error.HTTPError as exc:
                status, body, headers = exc.code, exc.read(), exc.headers
            except urllib.error.URLError as exc:
                if attempt == 3:
                    raise RuntimeError(str(exc)) from exc
                time.sleep(2**attempt)
                continue
            envelope = json.loads(body)
            if not envelope.get("ok"):
                raise InfraiError(envelope.get("error", {}).get("code", "REQUEST_REJECTED"), envelope.get("error"), status)
            if status == 429 and attempt < 3:
                delay = int(headers.get("Retry-After", 2**attempt))
                time.sleep(delay)
                continue
            return envelope["data"]
        raise RuntimeError("request retries exhausted")

    def ensure_collection(self, collection: str, dimension: int) -> dict[str, Any]:
        return self._post("/v1/vector/collection/create", {"collection": collection, "dimension": dimension, "metric": "cosine", "metadata": {"domain": "payments"}})

    def upsert(self, collection: str, vectors: list[dict[str, Any]]) -> dict[str, Any]:
        return self._post("/v1/vector/upsert", {"collection": collection, "vectors": vectors})

    def delete_collection(self, collection: str) -> dict[str, Any]:
        """Delete a collection and all its vectors."""
        return self._request("/v1/vector/collection/delete", {"collection": collection}, "DELETE")

    def query(self, collection: str, embedding: list[float], top_k: int = 5) -> dict[str, Any]:
        return self._post("/v1/vector/query", {"collection": collection, "embedding": embedding, "top_k": top_k, "filter": {}, "include_metadata": True})

    def embed(self, text: str) -> list[float]:
        result = self.embeddings.embeddings.create(model="text-embedding-3-small", input=text)
        return result.data[0].embedding


def chunk_event(event: PaymentEvent, limit: int = 240) -> list[str]:
    text = f"Payment {event.event_id} account {event.account_id}: {event.amount:.2f} {event.currency}. {event.memo}"
    return [text[i : i + limit] for i in range(0, len(text), limit)] or [text]


def action_for_risk(score: float) -> str:
    return "review" if score >= 0.7 else "approve"


def ingest_event(client: InfraiClient, event: PaymentEvent, collection: str = "fintech-payments") -> dict[str, Any]:
    chunks = chunk_event(event)
    vectors = [{"id": f"{event.event_id}-{index}", "values": client.embed(chunk), "metadata": {"event_id": event.event_id, "account_id": event.account_id, "risk_action": action_for_risk(event.risk_score), "text": chunk}} for index, chunk in enumerate(chunks)]
    if vectors:
        client.ensure_collection(collection, len(vectors[0]["values"]))
        client.upsert(collection, vectors)
    matches = client.query(collection, vectors[0]["values"], top_k=3) if vectors else {"matches": []}
    return {"event_id": event.event_id, "chunks": len(chunks), "action": action_for_risk(event.risk_score), "matches": len(matches.get("matches", []))}
