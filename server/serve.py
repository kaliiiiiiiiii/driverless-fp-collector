import json
import uuid
import faulthandler

import bson
import orjson
from aiohttp import web
from db import DataBase, _dir, logger
import logging


async def logger_middleware(request, handler):
    try:
        return await handler(request)
    except Exception as Argument:
        logger.exception("Error while handling request:")


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
            web.get("/favicon.ico", self.favicon),
            web.get("/example_page.html", self.example_page),
            web.get("/bundle.js", self.bundle),
            web.post('/api/v1/logger', self.api_log),
            web.get('/api/v1/compile', self.compile)
        ])

        app.on_cleanup.append(self._cleanup)
        app.on_startup.append(self._init)
        web.run_app(app, host="0.0.0.0", port=80)

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
            response.set_cookie("driverless-fp-collector", uuid.uuid4().hex, samesite='Lax')
        return response

    @staticmethod
    async def favicon(request: web.BaseRequest):
        return web.FileResponse(f"{_dir}/files/favicon.png")

    async def api_log(self, request: web.BaseRequest):
        data = await request.read()
        if len(data) > 500_000:
            raise ValueError("Got more than 500_000 data, aborting")
        ip = request.remote
        cookie = request.cookies.get("driverless-fp-collector")
        await self.db.add_fp_entry(ip, cookie, data)
        return web.Response(text='OK')

    async def compile(self, request: web.BaseRequest):
        query = request.query.get("q", {})
        if query:
            query = json.loads(query)
        if "_id" in query:
            del query["_id"]
        paths = await self.db.compile_paths(query)
        return web.Response(body=orjson.dumps(paths), content_type="application/json")


    @property
    def db(self) -> DataBase:
        return self._db


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    faulthandler.enable()
    server = Server()
    server.run()
