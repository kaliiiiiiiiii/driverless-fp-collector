import asyncio
import os
import time
import math
import typing
import uuid

import orjson

from concurrent import futures
from aiohttp import web
import motor.motor_asyncio
import pymongo.errors
import json
import faulthandler

_dir = os.path.dirname(os.path.abspath(__file__))


class DataBase:

    async def __aenter__(self, max_workers: int = 10):
        self._client = motor.motor_asyncio.AsyncIOMotorClient()
        self._db = self.client["fingerprints"]
        self._entries = self.db["a_entries"]

        self._paths = self.db["a_paths"]
        self._bots = self.db["bots"]
        self._windows = self.db["windows"]
        self._linux = self.db["linux"]
        self._ios = self.db["ios"]
        self._android = self.db["android"]
        self._mac = self.db["mac"]
        self._other = self.db["other"]

        self._ips = self.db["ips"]
        try:
            await self.db.validate_collection("entries")  # Try to validate a collection
        except pymongo.errors.OperationFailure:  # If the collection doesn't exist
            await self.entries.create_index("cookie", unique=True, name="cookie")
            await self.ips.create_index("ip", unique=True, name="ip")

            await self.paths.create_index("path", unique=True, name="paths")
            await self.windows.create_index("path", unique=True, name="paths")
            await self.bots.create_index("path", unique=True, name="paths")
            await self.linux.create_index("path", unique=True, name="paths")
            await self.ios.create_index("path", unique=True, name="paths")
            await self.android.create_index("path", unique=True, name="paths")
            await self.mac.create_index("path", unique=True, name="paths")
            await self.other.create_index("path", unique=True, name="paths")

        self._loop = asyncio.get_running_loop()
        self._pool = futures.ThreadPoolExecutor(max_workers=max_workers)
        self._paths_map = {}
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._pool.shutdown()
        self.client.close()

    async def _load_json(self, data: bytes):
        return await self._loop.run_in_executor(self._pool, lambda: orjson.loads(data))

    async def _dump_json(self, data) -> bytes:
        return await self._loop.run_in_executor(self._pool, lambda: orjson.dumps(data))

    async def _find_and_modify(self, collection: str, **kwargs):
        res = await self.db.command(
            'findAndModify',
            collection,
            **kwargs
        )
        value_doc = res.get("value")
        if value_doc:
            return value_doc
        elif res.get("lastErrorObject", {}).get("upserted"):
            return {"_id": res["lastErrorObject"]["upserted"]}
        else:
            raise Exception(res["lastErrorObject"])

    async def add_fp_entry(self, ip: str, cookie: str, fp: bytes):
        _time = math.floor(time.time())
        ip_doc = await self.ips.find_one({"ip": ip})
        collections = [self.paths]
        if ip_doc:
            if ip_doc["flag"] > 10:
                return
            timestamps: typing.List[int] = ip_doc["timestamps"]
            for idx, stamp in enumerate(timestamps):
                if stamp < (_time - 3_600):  # 60s*60min => 1h
                    timestamps.pop(idx)
            await self.ips.update_one({"ip": ip}, {"$push": {"timestamps": _time}})
            if len(timestamps) > 10:
                await self.ips.update_one({"ip": ip}, {"$inc": {"flag": 1}})
                return
        else:
            try:
                await self.ips.insert_one(
                    {"ip": ip, "timestamps": [_time], "flag": 0})
            except pymongo.errors.DuplicateKeyError:
                pass

        fp = await self._load_json(fp)

        platform = fp["HighEntropyValues"]["platform"]
        mobile = fp["HighEntropyValues"]["mobile"]
        is_bot = fp["is_bot"]

        if is_bot:
            collections.append(self.bots)
        elif mobile:
            if platform in ["Android", "null","Linux", "Linux aarch64",
                            "Linux armv5tejl", "Linux armv6l", "Linux armv7l", "Linux armv8l"]:
                collections.append(self.android)
            elif platform in ["iPhone", "iPod", "iPad"]:
                collections.append(self.ios)
            else:
                collections.append(self.other)
            collections.append(self.other)
        elif platform in ["OS/2", "Pocket PC", "Windows", "Win16", "Win32", "WinCE"]:
            collections.append(self.windows)
        elif platform in ["Macintosh", "MacIntel", "MacPPC", "Mac68K"]:
            collections.append(self.mac)
        elif platform in ["Linux", "Linux aarch64","Linux armv5tejl", "Linux armv6l", "Linux armv7l", "Linux armv8l",
                          "Linux i686", "Linux i686 on x86_64", "Linux ppc64", "Linux x86_64"]:
            collections.append(self.linux)
        else:
            collections.append(self.other)

        try:
            await self.entries.insert_one(
                {"ip": ip, "cookie": cookie, "fp": fp, "timestamp": _time})
        except pymongo.errors.DuplicateKeyError:
            pass
        else:
            cors = await self._loop.run_in_executor(self._pool, lambda: self.parse_paths(collections, fp))
            await asyncio.gather(*cors)

    def parse_paths(self, collections: typing.List[motor.motor_asyncio.AsyncIOMotorCollection],
                    entry, path: str = None) -> list:
        if path is None:
            path = ""
        else:
            path += "."
        cors = []
        for key, value in entry.items():
            if value is not None:
                serialized_key = json.dumps(key)
                current_path = path + serialized_key
                _type = type(value)

                if _type in [int, float, str, bool]:
                    cors.append(self._on_path(collections, current_path, [value], is_list=False))
                elif _type is list:
                    cors.append(self._on_path(collections, current_path, value, is_list=True))
                elif _type is dict:
                    cors.extend(self.parse_paths(collections, value, current_path))
                else:
                    raise ValueError(f"Unsupported type: {type(value)}")
        return cors

    async def _on_path(self, collections: typing.List[motor.motor_asyncio.AsyncIOMotorCollection], path: str,
                       values: typing.List[typing.Union[list, str, int, float, bool]],
                       is_list: bool = False):
        for collection in collections:
            try:
                await collection.insert_one({"path": path, "is_list": is_list})
            except pymongo.errors.DuplicateKeyError:
                pass
        for value in values:
            value = json.dumps(value).replace(".", "\uFF0E").replace("$", '\uFF04')
            for collection in collections:
                await collection.update_one(
                    {"path": path},
                    {"$inc": {f"values.{value}": 1}}
                )

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
    def paths(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._paths

    @property
    def windows(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._windows

    @property
    def linux(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._linux

    @property
    def ios(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._ios

    @property
    def mac(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._mac

    @property
    def android(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._android

    @property
    def bots(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._bots

    @property
    def other(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._other

    @property
    def ips(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._ips


class Server:

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
        app.add_routes([
            web.get("/", self.root),
            web.get("/iframe.html", self.iframe),
            web.get("/example_page.html", self.example_page),
            web.get("/bundle.js", self.bundle),
            web.post('/api/v1/logger', self.api_log)
        ])

        app.on_cleanup.append(self._cleanup)
        app.on_startup.append(self._init)
        web.run_app(app, host="0.0.0.0")

    async def root(self, request: web.BaseRequest):
        raise web.HTTPFound('example_page.html')

    @staticmethod
    async def bundle(request: web.BaseRequest):
        return web.FileResponse(f"{_dir}/files/bundle.js")

    @staticmethod
    async def example_page(request: web.BaseRequest):
        return web.FileResponse(f"{_dir}/files/example_page.html")

    @staticmethod
    async def iframe(request: web.BaseRequest):
        response = web.FileResponse(f"{_dir}/files/iframe.html")
        if not request.cookies.get("driverless-fp-collector"):
            response.set_cookie("driverless-fp-collector", uuid.uuid4().hex)
        return response

    async def api_log(self, request: web.BaseRequest):
        data = await request.read()
        ip = request.remote
        cookie = request.cookies.get("driverless-fp-collector")
        await self.db.add_fp_entry(ip, cookie, data)
        return web.Response(text='OK')

    @property
    def db(self) -> DataBase:
        return self._db


if __name__ == "__main__":
    faulthandler.enable()
    server = Server()
    server.run()
