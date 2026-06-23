# Remote docker auth logs

Auth Insight can SSH to remote docker hosts and tail SSO container logs (for
example Authelia) during a search. Local UCS logs are always queried; remote
hosts that fail to respond are skipped and reported in the UI.

## Configuration

Set UCR variable `authin/remote/hosts` to a JSON array:

```json
[
  {
    "name": "remote-sso",
    "host": "docker-host-a",
    "user": "deploy",
    "containers": [
      {"name": "authelia", "label": "Remote SSO"}
    ]
  },
  {
    "name": "internal-sso",
    "host": "docker-host-b",
    "user": "ops",
    "sudo": true,
    "containers": [
      {"name": "authelia", "label": "Internal SSO"}
    ]
  }
]
```

| Field | Purpose |
|-------|---------|
| `name` | Logical id shown in status messages |
| `host` | SSH hostname or `~/.ssh/config` alias |
| `user` | SSH user (optional if alias defines User) |
| `sudo` | Prefix `sudo -n docker logs` when true |
| `containers` | Docker container names to tail |

Enable with:

```bash
ucr set authin/remote/enabled=true
ucr set authin/remote/hosts='[...]'
systemctl restart univention-management-console-server
```

Site-specific host names belong in `.env` (see `.env.example`) and
`scripts/setup-remote-logs.sh`.

## Graceful degradation

If a remote host is offline, SSH fails, or `docker logs` errors:

- Local log search still completes
- The UMC **Remote log sources** panel lists each host as **available** or **unavailable**
- No module error dialog is shown for unreachable remotes

## Verify

```bash
sudo ./scripts/setup-remote-logs.sh
```

Then search in UMC **Auth Insight** and expand **Remote log sources**.

## Security

- Read-only `docker logs` only; container names are validated
- SSH uses `BatchMode=yes` (key-based auth required)
- Runs as root in the UMC module subprocess, same as local `/var/log/auth.log`

## Alternative: syslog forward

Forward container logs to a local file on the UCS host and add the path via
`authin/logs/extra`. See [syslog-authelia.md](syslog-authelia.md).
