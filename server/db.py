import motor.motor_asyncio
import pymongo.errors
import json

import orjson
import asyncio
import os
import time
import math
import typing
import uuid
import bson
import logging
from hashlib import sha1
from concurrent import futures
from collections import defaultdict

_dir = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger("driverless-fp-collector")
logging.basicConfig()


class DataBase:

    async def __aenter__(self, max_workers: int = 10):
        self._client = motor.motor_asyncio.AsyncIOMotorClient()
        self._db = self.client["fingerprints"]
        self._entries = self.db["entries"]
        self._values = self.db["values"]
        self._fingerprints = self.db["fingerprints"]
        self._val_map = {}

        self._ips = self.db["ips"]
        try:
            await self.db.validate_collection("entries")  # Try to validate a collection
        except pymongo.errors.OperationFailure:  # If the collection doesn't exist
            await self.entries.create_index("cookie", unique=True, name="cookie")
            await self.ips.create_index("ip", unique=True, name="ip")
            await self.values.create_index("v", unique=True, name="value")

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

    async def _index_value(self, value):
        value = json.dumps(value)
        _hash = sha1(value.encode()).hexdigest()
        val_id = self._val_map.get(_hash)
        if not val_id:
            try:
                res = await self.values.insert_one({"v": value})
                val_id = res.inserted_id
                self._val_map[_hash] = val_id
            except pymongo.errors.DuplicateKeyError:
                val_id = self._val_map.get(_hash)
                if not val_id:
                    res = await self.values.find_one({"v": value})
                    val_id = res.get("_id")
                    self._val_map[_hash] = val_id
        return val_id

    async def _get_value(self, value_id: bson.ObjectId, load_json:bool=True):
        value = await self.values.find_one({"_id": bson.ObjectId(value_id)})
        value = value.get("v")
        if not value:
            raise IndexError("Value isn't indexed in the database")
        if load_json:
            return json.loads(value)
        else:
            return value

    async def index_values(self, fp: typing.Union[list, str, int, float, dict], as_value: bool = False):
        _type = type(fp)
        if not as_value and _type is dict:
            _values = []
            _keys = fp.keys()
            _dict = {}
            for key, value in fp.items():
                _values.append(self.index_values(value))
            _values = await asyncio.gather(*_values)
            for key, value in zip(_keys, _values):
                _dict[key] = value
            return _dict
        elif not as_value and _type is list:
            _list = []
            for item in fp:
                _list.append(self.index_values(item, as_value=True))
            return await asyncio.gather(*_list)
        else:
            val_id = await self._index_value(fp)
            return val_id

    async def get_values(self, fp: typing.Union[list, bson.ObjectId, dict]):
        _type = type(fp)
        if _type is dict:
            _values = []
            _keys = []
            _dict = {}
            for key, value in fp.items():
                _values.append(self.get_values(value))
                if type(key) is bson.ObjectId:
                    _keys.append(self._get_value(key, load_json=False))
                else:
                    _keys.append(key)
            _values = await asyncio.gather(*_values)
            for key, value in zip(_keys, _values):
                _dict[key] = value
            return _dict
        elif _type is list:
            _list = []
            for item in fp:
                _list.append(self.get_values(item))
            return await asyncio.gather(*_list)
        elif _type is bson.ObjectId:
            val_id = await self._get_value(fp)
            return val_id
        else:
            return fp

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
            if cookie is None:
                cookie = "NoCookie_" + uuid.uuid4().hex
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

            pre_index = time.monotonic()
            parsed = await self.index_values(fp)
            parsed["_id"] = _id
            logger.debug(f"index values: {time.monotonic() - pre_index:_} s")
            await self.fingerprints.insert_one(parsed)

    def val2paths(self, values, path: str = None) -> typing.Iterable[typing.Union[str, any]]:
        _type = type(values)
        if _type is dict:
            if path is None:
                path = ""
            else:
                path += "."

            for key, value in values.items():
                serialized_key = json.dumps(key)
                current_path = path + serialized_key
                yield from self.val2paths(value, current_path)
        else:
            if path is None:
                path = ""
            yield path, values

    async def compile_paths(self, query:dict=None):
        if not query:
            query = {}

        query = await self.index_values(query)

        def parse_entry(_entry:dict, _paths:dict):
            for path, values in self.val2paths(_entry):
                if type(values) is list:
                    for value in values:
                        _paths[path][str(value)] += 1
                else:
                    _paths[path][str(values)] += 1
        paths = defaultdict(lambda:defaultdict(lambda: 0))

        coro = []
        async for entry in self.fingerprints.find(query):
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

    @property
    def values(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._values
