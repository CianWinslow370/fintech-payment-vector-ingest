import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / 'src'))
import run_ingest


@pytest.mark.parametrize('fail', [False, True])
def test_demo_cleans_its_collection_even_when_ingestion_fails(monkeypatch, fail):
    deleted = []
    collections = []

    class Client:
        def delete_collection(self, collection):
            deleted.append(collection)

    def ingest(client, event, collection):
        collections.append(collection)
        if fail:
            raise RuntimeError('query failed')
        return {'matches': 1}

    monkeypatch.setattr(run_ingest, 'InfraiClient', Client)
    monkeypatch.setattr(run_ingest, 'ingest_event', ingest)
    if fail:
        with pytest.raises(RuntimeError, match='query failed'):
            run_ingest.main()
    else:
        run_ingest.main()
    assert deleted == collections
    assert collections[0].startswith('fintech-demo-')
