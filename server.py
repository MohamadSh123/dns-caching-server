#!/usr/bin/env python3
"""
DNS caching server over UDP.

Resolves A records through upstream resolvers (8.8.8.8, 1.1.1.1), caches the
answers with an LRU eviction policy, honors record TTLs, persists the cache to
disk on shutdown and reports hit ratio and processing-time statistics.
"""

import socket
import sys
import time
import os
import dns.resolver
import dns.exception
from collections import OrderedDict
from datetime import datetime


SERVER_PORT = 5300
BUFFER_SIZE = 1024
CACHE_FILE = "dns_cache.txt"
DEFAULT_TTL = 3600
UPSTREAM_DNS = ["8.8.8.8", "1.1.1.1"]
MAX_CACHE_SIZE = 5
stats = {"requests": 0, "hits": 0, "misses": 0, "hit_time": 0.0, "miss_time": 0.0}


class DNSCache:

    def __init__(self, cache_file):
        self.cache_file = cache_file
        self.cache = OrderedDict()
        self.load_cache()

    def load_cache(self):
        if not os.path.exists(self.cache_file):
            return

        try:
            with open(self.cache_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(",")
                    if len(parts) == 5:
                        host, rtype, ips_str, ttl, ts = parts
                        exp_time = float(ts) + float(ttl)

                        if time.time() < exp_time:
                            answers_list = ips_str.split(";")
                            key = (host, rtype)
                            self.cache[key] = (answers_list, exp_time)
                            self.cache.move_to_end(key)
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] [LOG] cache Loaded from disk."
            )
        except Exception as e:
            print(f"[ERROR] cache Loading failed: {e}")

    def save_cache(self):
        try:
            with open(self.cache_file, "w") as f:
                for key, value in self.cache.items():
                    hostname, rtype = key
                    answers_list, exp_time = value

                    ttl = exp_time - time.time()
                    if ttl > 0:
                        ts = time.time()
                        ips_str = ";".join(answers_list)
                        f.write(f"{hostname},{rtype},{ips_str},{int(ttl)},{ts}\n")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [LOG] Cache saved to disk.")
        except Exception as e:
            print(f"[ERROR] cache Saving failed: {e}")

    def lookup(self, hostname, record_type="A"):
        key = (hostname, record_type)
        if key in self.cache:
            answers_list, exp_time = self.cache[key]
            if time.time() < exp_time:
                self.cache.move_to_end(key)
                remaining_ttl = int(exp_time - time.time())
                return answers_list, remaining_ttl
            else:
                del self.cache[key]

        return None, None

    def add(self, hostname, record_type, answers_list, ttl=DEFAULT_TTL):
        key = (hostname, record_type)
        exp_time = time.time() + float(ttl)

        if len(self.cache) >= MAX_CACHE_SIZE and key not in self.cache:
            self.cache.popitem(last=False)

        self.cache[key] = (answers_list, exp_time)
        self.cache.move_to_end(key)


def query_upstream_dns(hostname, record_type="A"):
    resolver = dns.resolver.Resolver()
    resolver.nameservers = UPSTREAM_DNS

    try:
        answers = resolver.resolve(hostname, record_type)
        ips = [r.to_text() for r in answers]
        ttl = answers.rrset.ttl
        # ttl = 10000
        return ips, ttl
    except Exception:
        return None, None


def parse_query(message):
    try:
        parts = message.split(" @ ", 1)
        cmd = parts[0].upper()
        data = parts[1] if len(parts) > 1 else ""

        if cmd == "RESOLVE":
            return data, "A"
        elif cmd == "SHOW_CACHE":
            return "SHOW_CACHE", None
        elif cmd == "CLEAR":
            return "CLEAR", None
        else:
            return None, None
    except:
        return None, None


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", SERVER_PORT))
    cache = DNSCache(CACHE_FILE)

    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] DNS Server UP on port {SERVER_PORT}"
    )
    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] Cache Policy: LRU, Max Size: {MAX_CACHE_SIZE}"
    )

    while True:
        try:
            msg, client_addr = sock.recvfrom(BUFFER_SIZE)
            t_start = time.perf_counter()
            timestamp_str = datetime.now().strftime("%H:%M:%S")

            decoded = msg.decode("utf-8")
            hostname, record_type = parse_query(decoded)

            stats["requests"] += 1
            response = ""
            is_hit = False

            if hostname == "SHOW_CACHE":
                if not cache.cache:
                    content = "Cache is empty."
                else:
                    lines = []
                    keys_to_delete = []
                    for key, val in cache.cache.items():
                        ttl = int(val[1] - time.time())
                        if ttl > 0:
                            ips_str = ", ".join(val[0])
                            lines.append(f"{key[0]} -> [{ips_str}] (TTL: {ttl}s)")
                        else:
                            keys_to_delete.append(key)

                    for k in keys_to_delete:
                        del cache.cache[k]

                    content = "\n".join(lines) if lines else "Cache is empty ."
                response = f"CACHE_CONTENTS:\n{content}"

            elif hostname == "CLEAR":
                cache.cache.clear()
                cache.save_cache()
                response = "CACHE_CLEARED: Cache wiped successfully."

            elif hostname is not None:
                answers_list, ttl = cache.lookup(hostname, record_type)

                if answers_list:
                    stats["hits"] += 1
                    is_hit = True
                    ips_str = ", ".join(answers_list)
                    response = f"OK:{ips_str} (TTL: {ttl}s - CACHE HIT)"
                else:
                    stats["misses"] += 1
                    is_hit = False
                    t_up_start = time.perf_counter()
                    answers_list, ttl = query_upstream_dns(hostname, record_type)
                    t_up_duration = time.perf_counter() - t_up_start

                    if answers_list:
                        cache.add(hostname, record_type, answers_list, ttl)
                        ips_str = ", ".join(answers_list)
                        response = f"OK:{ips_str} (TTL: {ttl}s - SERVER NEW)"
                        print(
                            f"[{timestamp_str}] [LOG] Upstream Query Time: {t_up_duration:.4f}s"
                        )
                    else:
                        response = f"ERROR: Could not resolve {hostname}"

            else:
                response = "ERROR: Unknown Command/Bad Format"

            sock.sendto(response.encode("utf-8"), client_addr)
            proc_time = time.perf_counter() - t_start

            if hostname not in ["SHOW_CACHE", "CLEAR"] and hostname is not None:
                if is_hit:
                    stats["hit_time"] += proc_time
                else:
                    stats["miss_time"] += proc_time

            print("-" * 50)
            print(f"[{timestamp_str}] Req #{stats['requests']} | Client: {client_addr}")
            print(f"Message: {decoded.strip()}")
            print(
                f"Action: {'HIT' if is_hit else 'MISS' if hostname not in ['SHOW_CACHE', 'CLEAR'] else 'CMD'}"
            )
            print(f"Proc Time: {proc_time:.6f}s")

            if stats["requests"] > 0:
                ratio = (stats["hits"] / stats["requests"]) * 100
                print(f"Stats -> Hit Ratio: {ratio:.1f}%")
                if stats["hits"] > 0:
                    print(
                        f"    -> Avg Hit Time: {(stats['hit_time'] / stats['hits']):.6f}s"
                    )
                if stats["misses"] > 0:
                    print(
                        f"    -> Avg Miss Time: {(stats['miss_time'] / stats['misses']):.6f}s"
                    )
            print("-" * 50)

        except KeyboardInterrupt:
            print("\nStopping server...")
            cache.save_cache()
            break
        except Exception as e:
            print(f"[ERROR] Server Error: {e}")


if __name__ == "__main__":
    main()
