# Performance expectations (smoke)

Informal targets for **single-entry lookup** on a developer machine. Measure with `curl` or `httpx` against a warm process (ZIM reader cached after first request).

| Backend | Typical `GET /words/{word}` | Notes |
|---------|----------------------------|--------|
| **SQL** (Postgres, indexed row) | ~5–30 ms | Depends on pool, network (local Docker vs host), and child-row load. |
| **ZIM** (cached `ZimReader`) | ~50–500 ms | libzim + HTML parse in a worker thread; first hit may open the archive. |
| **ZIM list** `GET /words` | seconds to minutes | Full-archive scan; use SQL + pagination for production listing. |

## Quick smoke commands

```bash
# SQL path (after ingest)
time curl -s -o /dev/null -H 'X-Data-Source: sql' http://127.0.0.1:8000/words/heval

# ZIM path
time curl -s -o /dev/null -H 'X-Data-Source: zim' http://127.0.0.1:8000/words/heval
```

Health checks should stay under ~100 ms when Postgres and ZIM are local and reachable.
