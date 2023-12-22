import asyncio
import os
import motor.motor_asyncio
from concurrent import futures

import orjson
from aiohttp import web
import datetime
import pymongo.errors
import ssl

_dir = os.path.dirname(os.path.abspath(__file__))

@web.middleware
async def static_headers(request: web.Request, handler):
    url = "http://10.165.180.101"
    response: web.Response = await handler(request)
    resource_name = request.match_info.route.name
    #if resource_name and resource_name.startswith('static'):
    response.headers.setdefault('Accept-CH', 'sec-ch-ua-platform, sec-ch-ua-arch, sec-ch-ua-model, '
                                                'sec-ch-ua-platform-version, sec-ch-ua-full-version, '
                                                'sec-ch-ua-bitness, sec-ch-ua-full-version-list, sec-ch-dpr')
    response.headers.setdefault("Referrer-Policy",'no-referrer')
    response.headers.setdefault("permissions-policy",f'ch-ua-bitness=(self), ch-ua-arch=(self), ch-ua-model=(self), '
                                                     f'ch-ua-platform=(self), ch-ua-platform-version=(self), '
                                                     f'ch-ua-full-version=(self), ch-ua-full-version-list=(self), '
                                                     f'ch-dpr=(self)')
    return response


class DataBase:

    async def __aenter__(self, max_workers: int = 5):
        self._client = motor.motor_asyncio.AsyncIOMotorClient()
        self._db = self.client["fingerprints"]
        self._entries = self.db["entries"]
        self._loop = asyncio.get_running_loop()
        self._pool = futures.ThreadPoolExecutor(max_workers=max_workers)
        # await self.entries.create_index({"ip": 1}, {"unique": "true"})
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
        app = web.Application(middlewares=[static_headers])
        app.add_routes(self.routes)
        app.add_routes([
            web.static('/', f"{_dir}/files", ),
            web.post('/api/v1/logger', self.api_log)
        ])

        app.on_cleanup.append(self._cleanup)
        app.on_startup.append(self._init)
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(r'D:\Projects\PyCharm\driverless-fp-collector\server\test_certs\private.key',
                                    "D:\Projects\PyCharm\driverless-fp-collector\server\test_certs\selfsigned.crt")
        web.run_app(app, host="0.0.0.0", ssl_context=ssl_context)

    # noinspection PyMethodParameters
    @routes.get("/")
    async def root(request: web.BaseRequest):
        raise web.HTTPFound('example_page.html')

    async def api_log(self, request: web.BaseRequest):
        data = await request.read()
        ip = request.remote
        try:
            await self.db.add_fp_entry(ip, data)
        except pymongo.errors.DuplicateKeyError:
            return web.Response(text='Fingerprint already in database', status=500)
        return web.Response(text='OK')

    @property
    def db(self) -> DataBase:
        return self._db


if __name__ == "__main__":
    server = Server()
    server.run()
