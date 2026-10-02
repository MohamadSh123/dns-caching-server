"""
Interactive client for the DNS caching server.

Sends RESOLVE, SHOW_CACHE and CLEAR commands over UDP and measures the
round-trip time (RTT) of every request.
"""

import socket
import time
import sys

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5300
BUFFER_SIZE = 4096
rtt_stats = []


def show_rtt_stats():
    if not rtt_stats:
        print("\n[INFO] No requests sent yet.")
        return

    print("\n" + "=" * 30)
    print("      RTT STATISTICS")
    print("=" * 30)

    total_rtt = 0
    for idx, rtt in enumerate(rtt_stats, 1):
        print(f"Request #{idx}: {rtt * 1000:.4f} ms")
        total_rtt += rtt

    avg_rtt = total_rtt / len(rtt_stats)
    print("-" * 30)
    print(f"Total Packets: {len(rtt_stats)}")
    print(f"Average RTT  : {avg_rtt * 1000:.4f} ms")
    print("=" * 30)


def send_request(sock, command, data=""):
    message = f"{command} @ {data}"

    try:
        start_time = time.perf_counter()
        sock.sendto(message.encode("utf-8"), (SERVER_IP, SERVER_PORT))
        sock.settimeout(5.0)
        response_bytes, _ = sock.recvfrom(BUFFER_SIZE)
        end_time = time.perf_counter()
        rtt = end_time - start_time
        rtt_stats.append(rtt)
        response_str = response_bytes.decode("utf-8")
        print(f"\n[SERVER]:\n{response_str}")
        print(f"[RTT]: {rtt * 1000:.4f} ms")

    except socket.timeout:
        print("\n[ERROR] Request timed out.")
    except Exception as e:
        print(f"\n[ERROR] Communication failed: {e}")


def print_menu():
    print("\n" + "=" * 35)
    print("      DNS CACHING CLIENT")
    print("=" * 35)
    print("  1. Resolve ")
    print("  2. ShowCache ")
    print("  3. ClearCache ")
    print("  4. ShowRTT ")
    print("  5. Exit")
    print("=" * 35)


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"Client started. Target: {SERVER_IP}:{SERVER_PORT}")
    while True:
        print_menu()
        choice = input("\nSelect (1-5): ").strip()

        if choice == "1":
            domain = input("Enter domain name: ").strip()
            if domain:
                send_request(sock, "RESOLVE", domain)
            else:
                print("Domain cannot be empty.")

        elif choice == "2":
            send_request(sock, "SHOW_CACHE")

        elif choice == "3":
            confirm = input("Confirm clear cache? (y/n): ").lower()
            if confirm == "y":
                send_request(sock, "CLEAR")

        elif choice == "4":
            show_rtt_stats()

        elif choice == "5":
            print("Exiting application.")
            sock.close()
            sys.exit(0)

        else:
            print("Invalid option.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nClient terminated.")
