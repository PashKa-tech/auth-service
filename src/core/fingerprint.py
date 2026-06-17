import hashlib

def calculate_device_fingerprint(
    user_agent: str | None,
    ip_address: str | None,
    accept_language: str | None = None
) -> str:
    """
    Calculate a lightweight SHA-256 fingerprint for a client session.
    Using IP subnet (e.g. /24 for IPv4, /64 for IPv6) to allow minor IP changes
    without breaking the session, while still binding it to the network area.
    """
    # Simple subnet calculation
    subnet = ""
    if ip_address:
        if ":" in ip_address:
            # IPv6: group first 4 blocks (64 bits)
            blocks = ip_address.split(":")
            subnet = ":".join(blocks[:4])
        elif "." in ip_address:
            # IPv4: class C subnet (24 bits)
            blocks = ip_address.split(".")
            subnet = ".".join(blocks[:3])
        else:
            subnet = ip_address

    ua = user_agent or "unknown"
    lang = accept_language or "unknown"
    
    raw_str = f"{ua}|{subnet}|{lang}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
