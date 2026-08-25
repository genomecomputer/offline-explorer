import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from prototype.selective_reader.server import LocalExplorerServer


class DesktopServerTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        workspace_root = Path(self.temporary_directory.name) / "workspaces"
        self.server = LocalExplorerServer(None, 0, workspace_root=workspace_root)
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.01},
            daemon=True,
        )
        self.server_thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)
        self.temporary_directory.cleanup()

    def request(self, desktop_token):
        body = json.dumps({"archive": "/tmp/not-a-genome.txt"})
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body.encode("utf-8"))),
            "Origin": self.server.origin,
        }
        if desktop_token is not None:
            headers["X-Offline-Explorer-Desktop"] = desktop_token
        connection.request(
            "POST",
            self.server.base_path + "/api/desktop/open",
            body=body,
            headers=headers,
        )
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        return response.status, payload

    def test_desktop_open_rejects_missing_capability(self):
        status, payload = self.request(None)
        self.assertEqual(status, 403)
        self.assertEqual(payload, {"error": "not found"})

    def test_desktop_open_rejects_an_invalid_file_after_authentication(self):
        status, payload = self.request(self.server.desktop_token)
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "choose a file ending in .genome.tar.gz")

    def test_desktop_server_uses_an_ephemeral_loopback_address(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertGreater(self.server.server_port, 0)
        self.assertTrue(self.server.url.startswith(self.server.origin))


if __name__ == "__main__":
    unittest.main()
