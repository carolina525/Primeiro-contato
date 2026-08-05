import asyncio
from bcb import http, sgs

async def main():
    try:
        results = await asyncio.gather(
            sgs.async_get(1),  # SELIC
            sgs.async_get(433),  # IPCA
        )
        return results
    finally:
        await http.aclose_async_client()

asyncio.run(main())