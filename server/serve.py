import uuid
import faulthandler

from aiohttp import web
from db import DataBase, _dir




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
            web.get("/api/v1/paths",self.paths),
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
            response.set_cookie("driverless-fp-collector", uuid.uuid4().hex, samesite='Lax')
        return response

    async def api_log(self, request: web.BaseRequest):
        data = await request.read()
        ip = request.remote
        cookie = request.cookies.get("driverless-fp-collector")
        await self.db.add_fp_entry(ip, cookie, data)
        return web.Response(text='OK')

    async def paths(self,request: web.BaseRequest):
        collection = request.query.get("collection")
        response = web.StreamResponse()
        response.content_type = "text/plain;charset=UTF-8"
        await response.prepare(request)
        document = None
        await response.write(b"[")
        async for _document in self.db.get_paths(collection):
            if document:
                await response.write(document+b",\n")
            # noinspection PyProtectedMember
            document = await self.db._dump_json(_document)
        if document:
            await response.write(document)
        await response.write(b"]")
        await response.write_eof()
        return response

    @property
    def db(self) -> DataBase:
        return self._db


if __name__ == "__main__":
    faulthandler.enable()
    server = Server()
    server.run()
