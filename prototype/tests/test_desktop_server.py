import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from prototype.selective_reader.server import (
    LocalExplorerServer,
    _shutdown_when_parent_pipe_closes,
)
from prototype.selective_reader.core import WorkspaceReport


class DesktopServerTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temporary_directory.name) / "workspaces"
        self.server = LocalExplorerServer(None, 0, workspace_root=self.workspace_root)
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

    def request(self, desktop_token, archive="/tmp/not-a-genome.txt"):
        body = json.dumps({"archive": archive})
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

    def post_json(self, route, payload):
        body = json.dumps(payload)
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request(
            "POST",
            self.server.base_path + route,
            body=body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body.encode("utf-8"))),
                "Origin": self.server.origin,
            },
        )
        response = connection.getresponse()
        response_payload = json.loads(response.read())
        connection.close()
        return response.status, response_payload

    def register_bundle(self):
        bundle_id = "a" * 20
        workspace = self.workspace_root / bundle_id
        workspace.mkdir(parents=True)
        (workspace / "retained.bin").write_bytes(b"cached bundle data")
        archive = Path(self.temporary_directory.name) / "source.genome.tar.gz"
        archive.write_bytes(b"original bundle")
        report = WorkspaceReport(
            archive=str(archive),
            workspace=str(workspace),
            schema_version="1.1.0",
            genome_build="GRCh38",
            generated_at="2026-08-31T00:00:00+00:00",
            extracted_files=1,
            extracted_bytes=18,
            skipped_files=0,
            skipped_bytes=0,
            validated_entries=1,
            elapsed_seconds=1.0,
            reused_workspace=False,
            validation_mode="full",
            validated_at="2026-08-31T00:01:00+00:00",
        )
        self.server.library.register(report)
        self.server.saved_results.add(
            bundle_id,
            "SYNTHETIC",
            {"section": "genes", "gene_symbol": "SYNTHETIC"},
        )
        return bundle_id, workspace, archive

    def test_desktop_open_rejects_missing_capability(self):
        status, payload = self.request(None)
        self.assertEqual(status, 403)
        self.assertEqual(payload, {"error": "not found"})

    def test_desktop_open_rejects_an_invalid_file_after_authentication(self):
        status, payload = self.request(self.server.desktop_token)
        self.assertEqual(status, 400)
        self.assertEqual(
            payload["error"],
            "choose a file ending in .genome.tar.gz or .genome.tar",
        )

    def test_desktop_open_accepts_a_genome_tar_path(self):
        archive = Path(self.temporary_directory.name) / "synthetic.genome.tar"
        archive.write_bytes(b"synthetic archive placeholder")

        status, _payload = self.request(self.server.desktop_token, str(archive))

        self.assertEqual(status, 202)

    def test_desktop_server_uses_an_ephemeral_loopback_address(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertGreater(self.server.server_port, 0)
        self.assertTrue(self.server.url.startswith(self.server.origin))

    def test_desktop_page_uses_the_embedded_sunflower_in_dark_mode(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("GET", self.server.base_path + "/")
        response = connection.getresponse()
        page = response.read().decode("utf-8")
        connection.close()

        self.assertEqual(response.status, 200)
        self.assertIn('<meta name="color-scheme" content="dark">', page)
        self.assertIn('src="data:image/png;base64,', page)
        self.assertNotIn("__SUNFLOWER_DATA_URI__", page)

    def test_remove_bundle_deletes_app_data_but_preserves_source_archive(self):
        bundle_id, workspace, archive = self.register_bundle()

        status, payload = self.post_json(
            "/api/library/remove",
            {"bundle_id": bundle_id},
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["bundles"], [])
        self.assertFalse(workspace.exists())
        self.assertTrue(archive.is_file())
        self.assertEqual(self.server.saved_results.entries(bundle_id), [])

    def test_remove_bundle_refuses_a_symlinked_workspace(self):
        bundle_id, workspace, _archive = self.register_bundle()
        outside = Path(self.temporary_directory.name) / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep")
        for child in workspace.iterdir():
            child.unlink()
        workspace.rmdir()
        workspace.symlink_to(outside, target_is_directory=True)

        status, payload = self.post_json(
            "/api/library/remove",
            {"bundle_id": bundle_id},
        )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "cached bundle workspace is unsafe")
        self.assertTrue((outside / "keep.txt").is_file())
        self.assertIsNotNone(self.server.library.find(bundle_id))


class ParentLivenessTest(unittest.TestCase):
    def test_parent_pipe_eof_requests_server_shutdown(self):
        shutdown_requested = threading.Event()

        class TestServer:
            def shutdown(self):
                shutdown_requested.set()

        read_fd, write_fd = os.pipe()
        monitor = threading.Thread(
            target=_shutdown_when_parent_pipe_closes,
            args=(TestServer(), read_fd),
            daemon=True,
        )
        monitor.start()

        os.close(write_fd)

        monitor.join(timeout=2)
        self.assertFalse(monitor.is_alive())
        self.assertTrue(shutdown_requested.is_set())


if __name__ == "__main__":
    unittest.main()
