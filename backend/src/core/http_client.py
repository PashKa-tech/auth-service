import httpx

# Global HTTP client to be shared across the application
# This prevents port exhaustion and enables connection pooling.
http_client: httpx.AsyncClient = None

async def init_http_client():
    global http_client
    http_client = httpx.AsyncClient(timeout=10.0)

async def close_http_client():
    global http_client
    if http_client:
        await http_client.aclose()
        http_client = None
