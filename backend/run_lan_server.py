"""Start the TaskFlow handoff API on one private LAN interface."""

import ipaddress
import os
import socket

import uvicorn

from backend.handoff_server import PAIRING_TOKEN, app


def _is_private_ipv4(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return address.version == 4 and address.is_private and not address.is_loopback


def find_lan_ipv4() -> str:
    configured_host = os.environ.get("TASKFLOW_BIND_HOST", "").strip()
    if configured_host:
        if not _is_private_ipv4(configured_host):
            raise RuntimeError(
                "TASKFLOW_BIND_HOST must be a private IPv4 address from your Wi-Fi network."
            )
        return configured_host

    candidates = []
    # Ask Windows which interface it would use for an outbound route. UDP
    # connect selects a local address but sends no packet to the destination.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            candidates.append(probe.getsockname()[0])
    except OSError:
        pass

    try:
        candidates.extend(
            result[4][0]
            for result in socket.getaddrinfo(
                socket.gethostname(), None, socket.AF_INET, socket.SOCK_DGRAM
            )
        )
    except OSError:
        pass

    for candidate in dict.fromkeys(candidates):
        if _is_private_ipv4(candidate):
            return candidate

    raise RuntimeError(
        "Could not find a private LAN IPv4 address. Connect this laptop to Wi-Fi, "
        "run ipconfig, then set TASKFLOW_BIND_HOST to the Wi-Fi IPv4 address."
    )


def main() -> None:
    host = find_lan_ipv4()
    port = int(os.environ.get("TASKFLOW_PORT", "8000"))
    if not 1 <= port <= 65535:
        raise RuntimeError("TASKFLOW_PORT must be between 1 and 65535.")

    print("TaskFlow same-Wi-Fi handoff server")
    print(f"Laptop address: http://{host}:{port}")
    print(f"Pairing token: {PAIRING_TOKEN}")
    print("Keep this console open while receiving handoffs.")
    print("Allow Python on Private networks only if Windows Firewall asks.", flush=True)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
