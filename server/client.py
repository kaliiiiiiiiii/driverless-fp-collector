import asyncio
import copy
import json
import traceback
import typing
from concurrent import futures

import aiohttp
import orjson


class Client:
    def __init__(self, host: str = "http://localhost:80", max_workers=5):
        self._host = host
        self._max_workers = max_workers
        self._val_cache = {}

    @staticmethod
    async def _get(url: str, params: dict = None) -> bytes:
        async with aiohttp.ClientSession() as r:
            async with r.get(url, params=params) as resp:
                assert resp.status == 200
                return await resp.read()

    async def compile(self, query: dict = None):
        if not query:
            query = {}
        res = await self._get(self.api_v1 + "/compile", params={"q": json.dumps(query)})
        return await self._load_json(res)

    @staticmethod
    def path2dict(paths: typing.Dict[str, typing.Dict[str, int]],
                  callback: typing.Callable[[str, typing.Dict[typing.Union[str, int], int]], typing.Union[str, int]]):
        _dict = {}

        def add_value(d, _path, _value):
            curr = d
            _path = json.loads(_path)
            k = _path[-1]
            _path = _path[:-1]
            for _key in _path:
                if _key not in curr:
                    curr[_key] = {}
                curr = curr[_key]
            curr[k] = _value
            return d

        _paths = []
        for path, values in paths.items():
            values = copy.deepcopy(values)

            # get n times, if is list
            n:typing.Union[typing.Dict[int, int], None] = values.get("l")
            if n:
                del values["l"]
                n:int = int(callback(path, n))
                _list = []
                for _ in range(n):
                    # todo: improve how list frequencies are calculated//handled
                    # more than once if is list
                    value = callback(path, values)
                    del values[value]
                    value = json.loads(value)
                    _list.append(value)
                add_value(_dict, path, _list)
            else:
                value = callback(path, values)
                if not value:
                    breakpoint()
                del values[value]
                value = json.loads(value)
                try:
                    add_value(_dict, path, value)
                except TypeError:
                    traceback.print_exc()
                    breakpoint()
        return _dict

    @staticmethod
    def opt_choose(path: str, values: typing.Dict[str, int]):
        _id = None
        count = 0
        for __id, _count in reversed(values.items()):
            if _count > count:
                _id = __id
                count = _count
        return _id

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
        paths = await c.compile({"type": "windows", "mainVersion": 120})
        _dict = c.path2dict(paths, c.opt_choose)
        _dict = c.path2dict(paths, c.opt_choose)
        print(_dict)


if __name__ == "__main__":
    asyncio.run(main())
