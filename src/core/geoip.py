def get_country_from_ip(ip_address: str | None) -> str:
    """Mock GeoIP lookup mapping IP addresses to countries.
    In production, this would use a MaxMind/GeoLite2 database reader or GeoIP API.
    """
    if not ip_address:
        return "Unknown"
        
    # Standard local addresses
    if ip_address in ("127.0.0.1", "localhost", "::1") or ip_address.startswith(("192.168.", "10.")):
        return "Local Network"
        
    # Helper mappings for testing anomaly detection
    mappings = {
        "1.1.1.1": "Australia",
        "8.8.8.8": "United States",
        "2.2.2.2": "France",
        "3.3.3.3": "Germany"
    }
    return mappings.get(ip_address, "Unknown")
