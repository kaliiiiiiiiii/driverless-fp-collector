import asyncio
import os
import motor.motor_asyncio
from concurrent import futures

import orjson
from aiohttp import web
import datetime

_dir = os.path.dirname(os.path.abspath(__file__))


class DataBase:

    async def __aenter__(self, max_workers: int = 5):
        self._client = motor.motor_asyncio.AsyncIOMotorClient()
        self._db = self.client["fingerprints"]
        self._entries = self.db["entries"]
        self._loop = asyncio.get_running_loop()
        self._pool = futures.ThreadPoolExecutor(max_workers=max_workers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._pool.shutdown()
        self.client.close()

    async def _load_json(self, data: bytes):
        return await self._loop.run_in_executor(self._pool, lambda: orjson.loads(data))

    async def _dump_json(self, data) -> bytes:
        return await self._loop.run_in_executor(self._pool, lambda: orjson.dumps(data))

    async def add_fp_entry(self, ip: str, fp: bytes):
        fp = await self._load_json(fp)
        await self.entries.insert_one({"ip": ip, "fp": fp, "timestamp": datetime.datetime.utcnow()})
    @property
    def client(self) -> motor.motor_asyncio.AsyncIOMotorClient:
        return self._client

    @property
    def db(self):
        return self._db

    @property
    def entries(self):
        return self._entries


class Server:
    routes = web.RouteTableDef()

    def __init__(self):
        pass

    # noinspection PyUnusedLocal
    async def _init(self, app):
        self._db = await DataBase().__aenter__()

    # noinspection PyUnusedLocal
    async def _cleanup(self, app):
        await self.db.__aexit__(None, None, None)

    def run(self):
        app = web.Application()
        app.add_routes(self.routes)
        app.add_routes([
            web.static('/', f"{_dir}/files"),
            web.post('/api/v1/logger', self.api_log)
        ])

        app.on_cleanup.append(self._cleanup)
        app.on_startup.append(self._init)
        web.run_app(app, host="localhost")

    # noinspection PyMethodParameters
    @routes.get("/")
    async def root(request: web.BaseRequest):
        raise web.HTTPFound('example_page.html')

    async def api_log(self, request: web.BaseRequest):
        data = await request.read()
        ip = request.remote
        await self.db.add_fp_entry(ip, data)
        return web.Response(text='OK')

    @property
    def db(self) -> DataBase:
        return self._db


if __name__ == "__main__":
    server = Server()
    server.run()
