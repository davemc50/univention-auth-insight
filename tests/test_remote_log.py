# SPDX-License-Identifier: AGPL-3.0-only

import json
import unittest
from unittest import mock

from authin import remote_log


class RemoteLogTests(unittest.TestCase):

    def test_parse_disabled(self):
        self.assertEqual(
            remote_log.parse_remote_sources_from_ucr(lambda key, default=None: default),
            [],
        )

    def test_parse_json_hosts(self):
        hosts = [
            {
                "name": "remote-sso",
                "host": "docker-host-a",
                "user": "deploy",
                "containers": [{"name": "authelia", "label": "Remote SSO"}],
            },
            {
                "name": "internal-sso",
                "host": "docker-host-b",
                "user": "ops",
                "sudo": True,
                "containers": ["authelia"],
            },
        ]

        def get_ucr(key, default=None):
            values = {
                "authin/remote/enabled": "true",
                "authin/remote/hosts": json.dumps(hosts),
            }
            return values.get(key, default)

        sources = remote_log.parse_remote_sources_from_ucr(get_ucr)
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0].host_id, "remote-sso")
        self.assertEqual(sources[0].label, "Remote SSO")
        self.assertTrue(sources[1].sudo)

    def test_parse_legacy_single_host(self):
        values = {
            "authin/remote/enabled": "true",
            "authin/remote/host": "docker-host-a",
            "authin/remote/user": "deploy",
            "authin/remote/containers": "authelia,proxy",
            "authin/remote/labels": "authelia=Remote SSO",
        }

        def get_ucr(key, default=None):
            return values.get(key, default)

        sources = remote_log.parse_remote_sources_from_ucr(get_ucr)
        self.assertEqual([item.container for item in sources], ["authelia", "proxy"])
        self.assertEqual(sources[0].label, "Remote SSO")

    @mock.patch("authin.remote_log.subprocess.run")
    def test_fetch_docker_logs(self, mock_run):
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout='time="2026-06-16T12:15:01+12:00" level=error msg="Unsuccessful 1FA authentication attempt by user \'user007\'"\n',
            stderr="",
        )
        source = remote_log.RemoteSource(
            host_id="remote-sso",
            host="docker-host-a",
            user="deploy",
            container="authelia",
        )
        lines = remote_log.fetch_docker_logs(source, max_lines=100)
        self.assertEqual(len(lines), 1)
        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd[0], "ssh")
        self.assertIn("deploy@docker-host-a", cmd)
        self.assertIn("docker logs --tail 100 authelia 2>&1", cmd[-1])

    @mock.patch("authin.remote_log.subprocess.run")
    def test_fetch_remote_logs_marks_unavailable(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=255, stdout="", stderr="connection refused")
        source = remote_log.RemoteSource(
            host_id="offline-host",
            host="offline.example.com",
            user="deploy",
            container="authelia",
            label="Offline SSO",
        )
        lines, statuses = remote_log.fetch_remote_logs([source], max_lines_per_container=100)
        self.assertEqual(lines, [])
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0].status, "unavailable")
        self.assertIn("connection refused", statuses[0].message)

    @mock.patch("authin.remote_log.subprocess.run")
    def test_fetch_remote_logs_partial_success(self, mock_run):
        ok_source = remote_log.RemoteSource(
            host_id="ok-host",
            host="online.example.com",
            user="deploy",
            container="authelia",
            label="Online SSO",
        )
        bad_source = remote_log.RemoteSource(
            host_id="bad-host",
            host="offline.example.com",
            user="deploy",
            container="authelia",
            label="Offline SSO",
        )

        def side_effect(cmd, **kwargs):
            joined = " ".join(cmd)
            if "online.example.com" in joined:
                return mock.Mock(
                    returncode=0,
                    stdout='time="2026-06-16T12:15:01+12:00" level=error msg="Unsuccessful 1FA authentication attempt by user \'user007\'"\n',
                    stderr="",
                )
            return mock.Mock(returncode=255, stdout="", stderr="timed out")

        mock_run.side_effect = side_effect
        lines, statuses = remote_log.fetch_remote_logs([ok_source, bad_source], max_lines_per_container=100)
        self.assertEqual(len(lines), 1)
        self.assertEqual(len(statuses), 2)
        self.assertEqual(statuses[0].status, "ok")
        self.assertEqual(statuses[1].status, "unavailable")

    def test_invalid_container_rejected(self):
        source = remote_log.RemoteSource(
            host_id="bad",
            host="host-a",
            user="deploy",
            container="bad;rm",
        )
        with self.assertRaises(remote_log.RemoteLogError):
            remote_log.fetch_docker_logs(source)


if __name__ == "__main__":
    unittest.main()
