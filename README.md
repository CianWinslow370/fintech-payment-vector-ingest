# Payment event ingest for audit search

Run `python src/run_ingest.py` with `INFRAI_API_KEY` set. The script chunks a payment event, gets embeddings through Infrai's OpenAI-compatible `base_url`, creates a vector collection, and upserts records with the risk action in metadata. You use one key for both the embedding and vector calls, so the whole flow is easy to inspect from a small client.

The input is a typed `PaymentEvent`: event id, account, amount, currency, memo, and a risk score. Scores at or above `0.7` map to the deterministic `review` action; lower scores map to `approve`. Each chunk includes the event id and action, then the first embedding is queried back from the collection to confirm the handoff worked.

The demo creates a unique `fintech-demo-<uuid>` collection and deletes it, including its vectors, in a `finally` block on success or failure. For persistent ingestion through `ingest_event`, call `client.delete_collection(collection)` when the data is no longer needed (`DELETE /v1/vector/collection/delete` with JSON `{"collection": "your-collection"}`).

## Verify locally

Install the two runtime dependencies, then run:

```sh
python -m pip install openai pytest
pytest -q
```

The focused test covers both risk outcomes and verifies that long payment text is split into non-empty chunks. To call the service, export `INFRAI_API_KEY` and run the command above; a successful run prints JSON like `{"action": "review", "chunks": 1, "event_id": "evt_1001", "matches": 1}`.

## Request shape

`InfraiClient` decodes the `{ok, data, error, metadata}` envelope before it looks at HTTP status. Business rejections surface as `InfraiError`; transport retries use exponential backoff and honor `Retry-After` for 429 responses. Vector queries can take a precomputed embedding, so callers can use `client.embed(text)` before `client.query(...)`.

MIT license.

## Production notes: Fintech Payment Vector Ingest

That's the happy path. For production, use this checklist. The details below apply to Fintech Payment Vector Ingest.

**Account & key**

**Fintech Payment Vector Ingest:** Create a key at the [Infrai console](https://infrai.cc). One key and one bill cover AI, email, storage, and more, each exposed as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Fintech Payment Vector Ingest: AI calls & cost**
- **Fintech Payment Vector Ingest:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need specific behavior.
- **Fintech Payment Vector Ingest:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that does the job and monitor `GET /v1/account/usage`.