import sys

import motor.motor_asyncio
import pymongo.errors
import json

import orjson
import asyncio
import os
import time
import math
import typing
import bson
import logging
from concurrent import futures
from collections import defaultdict

_dir = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger("driverless-fp-collector")
logging.basicConfig()


class DataBase:

    async def __aenter__(self, host:str=None,max_workers: int = 10):
        args = sys.argv
        if not host:
            if len(args) > 1:
                url = args[1]
            else:
                url = 'localhost:27017'
            host = [url]
        self._client = motor.motor_asyncio.AsyncIOMotorClient(host=host)
        self._db = self.client["fingerprints"]
        self._entries = self.db["entries"]
        self._fingerprints = self.db["fingerprints"]
        self._val_map = {}

        self._ips = self.db["ips"]
        try:
            await self.db.validate_collection("entries")  # Try to validate a collection
        except pymongo.errors.OperationFailure:  # If the collection doesn't exist
            await self.entries.create_index("cookie", unique=True, name="cookie")
            await self.ips.create_index("ip", unique=True, name="ip")

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

    async def add_fp_entry(self, ip: str, cookie: str, fp: bytes):
        _time = math.floor(time.time())
        ip_doc = await self.ips.find_one({"ip": ip})
        if ip_doc:
            if ip_doc["flag"] > 10:
                return
            timestamps: typing.List[int] = ip_doc["timestamps"]
            for idx, stamp in enumerate(timestamps):
                if stamp < (_time - 3_600):  # 60s*60min => 1h
                    timestamps.pop(idx)
            await self.ips.update_one({"ip": ip}, {"$push": {"timestamps": _time}})
            if len(timestamps) > 20:
                await self.ips.update_one({"ip": ip}, {"$inc": {"flag": 1}})
                return
        else:
            try:
                await self.ips.insert_one(
                    {"ip": ip, "timestamps": [_time], "flag": 0})
            except pymongo.errors.DuplicateKeyError:
                pass

        _id = bson.ObjectId()
        try:
            await self.entries.insert_one(
                {"ip": ip, "cookie": cookie, "fp": _id, "timestamp": _time})
        except pymongo.errors.DuplicateKeyError:
            pass
        else:
            pre_json = time.monotonic()
            fp = await self._load_json(fp)
            logger.debug(f"loading json took: {time.monotonic() - pre_json:_} s")
            if fp.get("status") != "pass":
                return
            platform = fp["HighEntropyValues"]["platform"]
            mobile = fp["HighEntropyValues"]["mobile"]
            is_bot = fp["is_bot"]
            fp["mainVersion"] = int(fp["HighEntropyValues"]["uaFullVersion"].split(".")[0])

            if is_bot:
                fp["type"] = "bot"
            if is_bot is True:
                pass
            elif mobile:
                if platform in ["Android", "null", "Linux", "Linux aarch64"] or platform[:10] == "Linux armv":
                    fp["type"] = "android"
                elif platform in ["iPhone", "iPod", "iPad"]:
                    fp["type"] = "ios"
                else:
                    fp["type"] = "other"
            elif platform in ["OS/2", "Pocket PC", "Windows", "Win16", "Win32", "WinCE"]:
                fp["type"] = "windows"
            elif platform in ["Macintosh", "MacIntel", "MacPPC", "Mac68K"]:
                fp["type"] = "mac"
            elif platform in ["Linux", "Linux aarch64", "Linux i686", "Linux i686 on x86_64",
                              "Linux ppc64", "Linux x86_64"] or platform[:10] == "Linux armv":
                fp["type"] = "linux"
                fp["type"] = "other"
            fp["_id"] = _id
            await self.fingerprints.insert_one(fp)

    def val2paths(self, values, path: list = None) -> typing.Iterable[typing.Union[str, any]]:
        _type = type(values)
        if _type is dict:
            if path is None:
                path = []

            for key, value in values.items():
                curr_path = path + [key]
                yield from self.val2paths(value, curr_path)
        else:
            if path:
                yield json.dumps(path), values

    async def compile_paths(self, query:dict=None):
        if not query:
            query = {}

        def parse_entry(_entry:dict, _paths:dict):
            for path, values in self.val2paths(_entry):
                if type(values) is list:
                    for value in values:
                        _paths[path][json.dumps(value)] += 1
                    if "l" not in _paths[path]:
                        _paths[path]["l"] = defaultdict(lambda: 0)
                    _paths[path]["l"][str(len(values))] += 1
                else:
                    _paths[path][json.dumps(values)] += 1
        paths = defaultdict(lambda:defaultdict(lambda: 0))

        coro = []
        async for entry in self.fingerprints.find(query):
            del entry["_id"]
            coro.append(self._loop.run_in_executor(self._pool, lambda: parse_entry(entry, paths)))
        await asyncio.gather(*coro)
        return paths

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
    def fingerprints(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._fingerprints

    @property
    def ips(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._ips
