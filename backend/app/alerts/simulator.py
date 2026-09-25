"""Real-time live attack simulator for AI SOC RAG dashboard."""

import argparse
import random
import time
from datetime import datetime, timezone
import requests

ATTACK_TEMPLATES = [
    {
        "attack_type": "PortScan",
        "protocol": "TCP",
        "destination_port": 443,
        "severity": "High",
        "description": "Real-time automated port sweep detected on perimeter firewall.",
    },
    {
        "attack_type": "SSH-Bruteforce",
        "protocol": "TCP",
        "destination_port": 22,
        "severity": "Critical",
        "description": "Real-time automated SSH credential brute-forcing attempt.",
    },
    {
        "attack_type": "DDoS-HTTP-Flood",
        "protocol": "TCP",
        "destination_port": 80,
        "severity": "Critical",
        "description": "High frequency request burst targeting web application ingress.",
    },
    {
        "attack_type": "SqlInjection",
        "protocol": "TCP",
        "destination_port": 443,
        "severity": "High",
        "description": "Web Application Firewall detected SQL control syntax payload.",
    },
    {
        "attack_type": "Botnet-C2",
        "protocol": "TCP",
        "destination_port": 8080,
        "severity": "High",
        "description": "Periodic outbound beaconing to malicious external IP.",
    },
    {
        "attack_type": "Web-XSS",
        "protocol": "TCP",
        "destination_port": 80,
        "severity": "Medium",
        "description": "Script injection attempt in URI query parameter.",
    },
]

SOURCE_IPS = ["192.168.1.105", "185.220.101.4", "45.33.32.156", "198.51.100.44", "203.0.113.12", "192.168.1.200"]
DEST_IPS = ["10.0.0.15", "10.0.0.8", "10.0.0.12", "10.0.0.20", "10.0.0.2"]


def run_simulator(backend_url: str, interval: int, token: str = None):
    """Periodically push simulated network security alerts to FastAPI backend."""
    url = f"{backend_url.rstrip('/')}/alerts"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print(f"Starting Live Alert Simulator targeting {url} (interval: {interval}s)...")
    print("Press Ctrl+C to stop.\n")

    count = 0
    try:
        while True:
            template = random.choice(ATTACK_TEMPLATES)
            src_ip = random.choice(SOURCE_IPS)
            dst_ip = random.choice(DEST_IPS)
            src_port = random.randint(1024, 65535)
            confidence = round(random.uniform(0.70, 0.99), 2)

            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source_ip": src_ip,
                "destination_ip": dst_ip,
                "source_port": src_port,
                "destination_port": template["destination_port"],
                "protocol": template["protocol"],
                "attack_type": template["attack_type"],
                "confidence": confidence,
                "severity": template["severity"],
                "description": template["description"],
            }

            try:
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                if response.status_code == 201:
                    count += 1
                    data = response.json()
                    print(f"[{count}] Alert Generated: {data['attack_type']} ({data['severity']}) from {data['source_ip']} -> {data['destination_ip']}:{data['destination_port']}")
                else:
                    print(f"Error {response.status_code}: {response.text}")
            except Exception as e:
                print(f"Connection error: {e}")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nSimulator stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI SOC Real-time Live Alert Simulator")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--interval", type=int, default=15, help="Alert generation interval in seconds")
    parser.add_argument("--token", default=None, help="Optional JWT bearer token for authenticated endpoints")
    args = parser.parse_args()

    run_simulator(args.url, args.interval, args.token)
