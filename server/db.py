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
from hashlib import sha1
from concurrent import futures

_dir = os.path.dirname(os.path.abspath(__file__))


class DataBase:

    async def __aenter__(self, max_workers: int = 10):
        self._client = motor.motor_asyncio.AsyncIOMotorClient()
        self._db = self.client["fingerprints"]
        self._entries = self.db["a_entries"]
        self._values = self.db["a_values"]
        self._val_map = {}

        self._all_path_collections = ["a_paths", "bots", "windows", "linux", "ios", "android", "mac", "other"]

        self._paths = self.db["a_paths"]
        self._bots = self.db["bots"]
        self._windows = self.db["windows"]
        self._linux = self.db["linux"]
        self._ios = self.db["ios"]
        self._android = self.db["android"]
        self._mac = self.db["mac"]
        self._other = self.db["other"]

        self._ips = self.db["a_ips"]
        try:
            await self.db.validate_collection("entries")  # Try to validate a collection
        except pymongo.errors.OperationFailure:  # If the collection doesn't exist
            await self.entries.create_index("cookie", unique=True, name="cookie")
            await self.ips.create_index("ip", unique=True, name="ip")
            await self.values.create_index("v", unique=True, name="value")
            for name in self._all_path_collections:
                await self.db[name].create_index("p", unique=True, name="paths")

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

    async def get_value(self, value_id: bson.ObjectId):
        value = await self.values.find_one({"_id": bson.ObjectId(value_id)})
        value = value.get("v")
        if not value:
            raise IndexError("Value isn't indexed in the database")
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
            if len(timestamps) > 20:
                await self.ips.update_one({"ip": ip}, {"$inc": {"flag": 1}})
                return
        else:
            try:
                await self.ips.insert_one(
                    {"ip": ip, "timestamps": [_time], "flag": 0})
            except pymongo.errors.DuplicateKeyError:
                pass

        pre_json = time.monotonic()
        fp = await self._load_json(fp)
        pre_index = time.monotonic()
        print(f"loading json took: {pre_index-pre_json:_} s")
        parsed = await self.index_values(fp)
        print(f"index values: {time.monotonic() - pre_json:_} s")
        if fp.get("status") != "pass":
            return
        if cookie is None:
            cookie = "NoCookie_" + uuid.uuid4().hex
        platform = fp["HighEntropyValues"]["platform"]
        mobile = fp["HighEntropyValues"]["mobile"]
        is_bot = fp["is_bot"]

        if is_bot:
            collections.append(self.bots)
        if is_bot is True:
            pass
        elif mobile:
            if platform in ["Android", "null", "Linux", "Linux aarch64"] or platform[:10] == "Linux armv":
                collections.append(self.android)
            elif platform in ["iPhone", "iPod", "iPad"]:
                collections.append(self.ios)
            else:
                collections.append(self.other)
        elif platform in ["OS/2", "Pocket PC", "Windows", "Win16", "Win32", "WinCE"]:
            collections.append(self.windows)
        elif platform in ["Macintosh", "MacIntel", "MacPPC", "Mac68K"]:
            collections.append(self.mac)
        elif platform in ["Linux", "Linux aarch64", "Linux i686", "Linux i686 on x86_64",
                          "Linux ppc64", "Linux x86_64"] or platform[:10] == "Linux armv":
            collections.append(self.linux)
        else:
            collections.append(self.other)

        try:
            await self.entries.insert_one(
                {"ip": ip, "cookie": cookie, "fp": parsed, "timestamp": _time})
        except pymongo.errors.DuplicateKeyError:
            pass
        else:
            pre_paths = time.monotonic()
            cors = await self._loop.run_in_executor(self._pool, lambda: self.make_paths_futures(collections, parsed))
            pre_save = time.monotonic()
            print(f"val2paths took: {pre_save - pre_paths:_} s")
            await asyncio.gather(*cors)
            print(f"saving paths took: {time.monotonic() -pre_save:_} s")
            return

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

    def make_paths_futures(self, collections: typing.List[motor.motor_asyncio.AsyncIOMotorCollection],parsed) -> typing.List[asyncio.Task]:
        cors = []
        for path, value in self.val2paths(parsed):
            if type(value) is list:
                is_list = True
            else:
                is_list = False
                value = [value]
            cors.append(self._loop.create_task(self._on_path(collections, path, value, is_list=is_list)))
        return cors

    @staticmethod
    async def _on_path(collections: typing.List[motor.motor_asyncio.AsyncIOMotorCollection], path: str,
                       values: typing.List[typing.Union[list, str, int, float, bool]],
                       is_list: bool = False):
        for collection in collections:
            try:
                await collection.insert_one({"p": path, "l": is_list})
            except pymongo.errors.DuplicateKeyError:
                pass
        coro_s = []
        for val_id in values:
            if type(val_id) is not bson.ObjectId:
                raise ValueError("got other than ObjectId as id")
            for collection in collections:
                coro_s.append(collection.update_one(
                    {"p": path},
                    {"$inc": {f"v.{val_id}": 1}}
                ))
        await asyncio.gather(*coro_s)

    async def _process_path_document(self, document: typing.Dict[str, typing.Union[typing.Dict[str, str], str]]) -> \
    typing.Tuple[
        str, typing.Dict[str, str]]:
        path = document["p"]
        values = {}
        for val_id, count in document["v"].items():
            value = await self.get_value(bson.ObjectId(val_id))
            values[value] = count

        return path, values

    async def get_paths(self, collection: str = None) -> typing.AsyncIterable[typing.Tuple[str, typing.Dict[str, str]]]:
        if collection is None:
            collection = "a_paths"
        assert collection in self._all_path_collections
        async for document in self.db[collection].find():
            document = await self._process_path_document(document)
            yield document

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

    @property
    def values(self) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return self._values
