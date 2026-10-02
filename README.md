# DNS Caching Server

A client and server pair over UDP that resolves domain names through upstream DNS resolvers and caches the answers locally.

## Features

- **LRU cache** built on `OrderedDict`, with a configurable maximum size.
- **TTL handling:** each record keeps the TTL returned by the upstream resolver and expires on time.
- **Persistence:** the cache is saved to disk on shutdown and reloaded on startup, skipping expired records.
- **Statistics:** hit ratio, average processing time for hits and misses, and per-request logging.
- **Client:** interactive menu with resolve, show cache, clear cache and round-trip time (RTT) statistics.

## Protocol

Text messages over UDP port 5300, in the form `COMMAND @ DATA`:

| Command | Example | Response |
| --- | --- | --- |
| `RESOLVE` | `RESOLVE @ google.com` | `OK:<ips> (TTL: <s> - CACHE HIT \| SERVER NEW)` |
| `SHOW_CACHE` | `SHOW_CACHE @ ` | Cache contents with remaining TTLs |
| `CLEAR` | `CLEAR @ ` | `CACHE_CLEARED: ...` |

## Results

Measured from the client across 10 domains, with cache sizes of 5, 10 and 20:

- **Cache miss:** roughly 10 to 60 ms per request, with spikes up to about 475 ms.
- **Cache hit:** roughly 0.2 to 0.6 ms, about 100 times faster.
- **LRU behavior:** with a cache of 5 and 10 distinct domains, the second round misses on the first five domains, since they were evicted while the last five were inserted.

## Getting started

```bash
pip install -r requirements.txt
python server.py          # terminal 1
python client.py          # terminal 2
```

## Roadmap

- [ ] Support the standard DNS wire format (RFC 1035) so tools like `dig @127.0.0.1 -p 5300 google.com` work against the server.
- [ ] Handle requests concurrently.
- [ ] Add unit tests for LRU eviction and TTL expiry.
- [ ] Move configuration (port, cache size, upstream resolvers) to command-line arguments.

## About

Built for the Computer Networks course in the B.Sc. in Information Systems, University of Haifa, 2026.
