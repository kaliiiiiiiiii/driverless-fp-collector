import json

import aiohttp
from concurrent import futures
import asyncio
import orjson


class Client:
    def __init__(self, host: str = "http://localhost:8080", max_workers=5):
        self._host = host
        self._max_workers = max_workers

    async def get(self, url: str, params: dict = None) -> bytes:
        async with aiohttp.ClientSession() as r:
            async with r.get(url, params=params) as resp:
                assert resp.status == 200
                return await resp.read()

    async def compile(self, query:dict=None):
        if not query:
            query = {}
        res = await self.get(self.api_v1 + "/compile", params={"q": json.dumps(query)})
        return await self._load_json(res)

    async def __aenter__(self):
        self._pool = futures.ThreadPoolExecutor(max_workers=self._max_workers)
        self._loop = asyncio.get_running_loop()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._pool.shutdown()

    async def _load_json(self, data: bytes):
        return await self._loop.run_in_executor(self._pool, lambda: orjson.loads(data))

    async def _dump_json(self, data) -> bytes:
        return await self._loop.run_in_executor(self._pool, lambda: orjson.dumps(data))

    @property
    def host(self) -> str:
        return self._host

    @property
    def api_v1(self) -> str:
        return self.host + "/api/v1"


async def main():
    async with Client() as c:
        paths = await c.compile({"type": "windows", "mainVersion":120})
        print(paths)

if __name__ == "__main__":
    asyncio.run(main())

