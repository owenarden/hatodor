"""Canvas pagination and the SP API envelope, against local fake servers."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from clarifier.canvas import Canvas, CanvasError
from clarifier.sp import SP, SPError, task_key


class FakeServer:
    def __init__(self, handler):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class CanvasHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        if self.headers.get("Authorization") != "Bearer tok":
            self.send_response(401)
            self.end_headers()
            return
        if u.path == "/api/v1/courses/1/assignments":
            page = int(parse_qs(u.query).get("page", ["1"])[0])
            body = [{"id": page * 10 + i} for i in range(2)]
            self.send_response(200)
            if page < 3:
                host = f"http://{self.headers['Host']}"
                self.send_header("Link", f'<{host}/api/v1/courses/1/assignments?page={page + 1}>; '
                                         f'rel="next", <{host}/x>; rel="last"')
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())
        else:
            self.send_response(404)
            self.end_headers()


class SPHandler(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *a):
        pass

    def _reply(self, code, payload):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/projects":
            self._reply(200, {"ok": True, "data": [{"id": "p9", "title": "School"},
                                                   {"id": "p1", "title": "School Admin"}]})
        elif u.path == "/tasks":
            src = q.get("source", ["active"])[0]
            self._reply(200, {"ok": True, "data": [{"id": f"{src}-1", "notes": "x"}]})
        else:
            self._reply(404, {"ok": False, "error": {"code": "NOT_FOUND", "message": "nope"}})

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        SPHandler.requests.append(("POST", self.path, json.loads(self.rfile.read(n))))
        self._reply(201, {"ok": True, "data": {"id": "new1"}})

    def do_PATCH(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n))
        if "deadlineDay" in body and "deadlineWithTime" in body and body["deadlineDay"] \
                and body["deadlineWithTime"]:
            self._reply(400, {"ok": False, "error": {"code": "INVALID_INPUT", "message": "both"}})
            return
        SPHandler.requests.append(("PATCH", self.path, body))
        self._reply(200, {"ok": True, "data": {"id": "t1"}})


class ClientTests(unittest.TestCase):
    def test_canvas_follows_every_page(self):
        srv = FakeServer(CanvasHandler)
        try:
            ids = [a["id"] for a in Canvas(srv.url, "tok").get("/courses/1/assignments")]
            self.assertEqual(ids, [10, 11, 20, 21, 30, 31])
            with self.assertRaises(CanvasError):
                Canvas(srv.url, "wrong").get("/courses/1/assignments")
        finally:
            srv.close()

    def test_sp_reads_and_writes(self):
        SPHandler.requests = []
        srv = FakeServer(SPHandler)
        try:
            sp = SP(srv.url, dry_run=False)
            self.assertEqual(sp.project_id("school"), "p9")      # exact title match only
            tasks = sp.tasks("p9")
            self.assertEqual([t["id"] for t in tasks], ["active-1", "archived-1"])
            self.assertTrue(tasks[1]["_archived"])
            self.assertEqual(sp.create({"title": "Math: #3 worksheet"}), "new1")
            sp.update("t1", {"title": "x", "deadlineWithTime": 1}, "x")
            method, path, body = SPHandler.requests[0]
            self.assertTrue(body["isIgnoreShortSyntax"])
            self.assertTrue(SPHandler.requests[1][2]["isIgnoreShortSyntax"])
            with self.assertRaises(SPError) as ctx:
                sp._req("GET", "/missing")
            self.assertIn("NOT_FOUND", str(ctx.exception))
        finally:
            srv.close()

    def test_dry_run_makes_no_requests(self):
        SPHandler.requests = []
        srv = FakeServer(SPHandler)
        try:
            sp = SP(srv.url, dry_run=True)
            self.assertIsNone(sp.create({"title": "t"}))
            sp.update("t1", {"isDone": True}, "t")
            self.assertEqual(SPHandler.requests, [])
            self.assertEqual(len(sp.log), 2)
        finally:
            srv.close()

    def test_task_key(self):
        self.assertEqual(task_key({"notes": "Canvas: graded\nclarifier:key=canvas:assignment:5\n"}),
                         "canvas:assignment:5")
        self.assertIsNone(task_key({"notes": None}))


if __name__ == "__main__":
    unittest.main()
