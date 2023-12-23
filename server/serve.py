import asyncio
import os
import datetime
import orjson

from concurrent import futures
from aiohttp import web
import motor.motor_asyncio
import pymongo.errors
import json

_dir = os.path.dirname(os.path.abspath(__file__))


class DataBase:

    async def __aenter__(self, max_workers: int = 5):
        self._client = motor.motor_asyncio.AsyncIOMotorClient()
        self._db = self.client["fingerprints"]
        self._entries = self.db["entries"]
        self._stats = self.db["stats"]
        try:
            await self.db.validate_collection("entries")  # Try to validate a collection
        except pymongo.errors.OperationFailure:  # If the collection doesn't exist
            await self.entries.create_index("ip", unique=True, name="ip", )
            await self.stats.insert_one({})
        self._loop = asyncio.get_running_loop()
        self._pool = futures.ThreadPoolExecutor(max_workers=max_workers)
        await self.entries.create_index("ip", unique=True, name="ip", )
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
        try:
            await self.entries.insert_one({"ip": ip, "fp": fp, "timestamp": datetime.datetime.utcnow()})
            stats = await self.stats.find_one({})
            stats = await self._loop.run_in_executor(self._pool, lambda: self.update_stats(entry=fp, stats=stats))
            await self.stats.find_one_and_replace({},stats)
        except pymongo.errors.DuplicateKeyError:
            pass

    def update_stats(self, entry, stats=None, path: str = ""):
        if stats is None:
            stats = {}
        for key, value in entry.items():
            if value is not None:
                serialized_key = json.dumps(key)
                if path:
                    path += "."
                current_path = path + serialized_key
                _type = type(value)

                if _type in [int, float, str, bool]:
                    stats_key = current_path + "." + json.dumps(value)
                    if stats_key not in stats:
                        stats[stats_key] = 1
                    else:
                        stats[stats_key] += 1
                elif _type is dict:
                    stats = self.update_stats(value, stats, current_path)
                elif _type is list:
                    for item in value:
                        sub_key = current_path + ".[" + json.dumps(item) + "]"
                        if sub_key not in stats:
                            stats[sub_key] = 1
                        else:
                            stats[sub_key] += 1
                        if type(item) is dict:
                            stats = self.update_stats(item, stats, current_path)
                else:
                    raise ValueError(f"Unsupported type: {type(value)}")

        return stats



    @property
    def client(self) -> motor.motor_asyncio.AsyncIOMotorClient:
        return self._client

    @property
    def db(self) -> motor.motor_asyncio.AsyncIOMotorDatabase:
        return self._db

    @property
    def entries(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._entries

    @property
    def stats(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._stats


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
            web.static('/', f"{_dir}/files", ),
            web.post('/api/v1/logger', self.api_log)
        ])

        app.on_cleanup.append(self._cleanup)
        app.on_startup.append(self._init)
        web.run_app(app, host="0.0.0.0")

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
