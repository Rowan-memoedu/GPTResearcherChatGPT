"""Let upstream URL checks validate public DNS behind a local Fake-IP proxy.

Only the URL-security module receives this resolver. HTTP connections retain
the system resolver and proxy routing. Private URLs remain disabled.
"""
from functools import lru_cache
import ipaddress
import socket
import time
import types

import requests

FAKE_IP_RANGE = ipaddress.ip_network("198.18.0.0/15")
SYSTEM_RESOLVER = socket.getaddrinfo


@lru_cache(maxsize=256)
def public_addresses(host: str, time_bucket: int) -> tuple[str, ...]:
    addresses = []
    try:
        for record_type in ("A", "AAAA"):
            response = requests.get(
                "https://dns.google/resolve",
                params={"name": host, "type": record_type, "edns_client_subnet": "0.0.0.0/0"},
                timeout=12, allow_redirects=False,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("Status") != 0 or data.get("TC"):
                raise ValueError("Public DNS query failed")
            addresses.extend(record["data"] for record in data.get("Answer", []) if record.get("type") in (1, 28))
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise ValueError("Public DNS did not confirm public addresses")
    except Exception:
        raise socket.gaierror("Public DNS verification failed") from None
    return tuple(dict.fromkeys(addresses))


def validation_resolver(host, port, *args, **kwargs):
    original = SYSTEM_RESOLVER(host, port, *args, **kwargs)
    resolved = [ipaddress.ip_address(item[4][0]) for item in original]
    fake = [ip.version == 4 and ip in FAKE_IP_RANGE for ip in resolved]
    if not any(fake):
        return original
    # An IP literal or a mixed private result must keep the upstream rejection.
    try:
        ipaddress.ip_address(host)
        return original
    except ValueError:
        pass
    if any(not is_fake and not ip.is_global for ip, is_fake in zip(resolved, fake)):
        return original
    normalized = host.rstrip(".").encode("idna").decode("ascii")
    if "." not in normalized or normalized.lower().endswith((".local", ".localhost", ".internal")):
        return original
    addresses = public_addresses(normalized, int(time.monotonic() // 30))
    return [
        (socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM,
         socket.IPPROTO_TCP, "", (address, port or 0))
        for address in addresses
    ]


def install_proxy_dns_validation():
    from gpt_researcher.utils import url_security
    # Replace the module's socket binding, never socket.getaddrinfo globally.
    url_security.socket = types.SimpleNamespace(getaddrinfo=validation_resolver, gaierror=socket.gaierror)
