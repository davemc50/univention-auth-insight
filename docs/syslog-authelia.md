# Forward Authelia auth logs via syslog

Authelia docker containers write structured login failures to stdout. Auth
Insight on a UCS host can read them either by:

1. **SSH docker logs** — see [remote-docker-logs.md](remote-docker-logs.md)
2. **Syslog forward** — one-way push to a local file (below)

## Recommended layout (syslog)

```text
docker host (Authelia) → rsyslog → UCS host:/var/log/authelia/auth.log
                                 → authin via UCR authin/logs/extra
```

## Source host — Authelia → syslog

1. Configure Authelia file or stdout logging (default docker logs is fine).
2. Add **promtail**, **fluent-bit**, or **rsyslog** imfile on the docker log path, **or**
   set Authelia `log_file_path` to a host-mounted volume.

Example **rsyslog** forwarder on the docker host (`/etc/rsyslog.d/authelia-forward.conf`):

```rsyslog
input(type="imfile"
      File="/var/lib/docker/containers/*/*-json.log"
      Tag="authelia"
      readMode="2")

if $programname == 'authelia' then @@ucs-primary.example.com:514
& stop
```

Use a dedicated tag/filter so only Authelia lines are forwarded.

## UCS host — receive and store

`/etc/rsyslog.d/authelia-remote.conf`:

```rsyslog
module(load="imudp")
input(type="imudp" port="514")

if $fromhost-ip == '10.0.0.11' and $programname == 'authelia' then {
    action(type="omfile" file="/var/log/authelia/auth.log")
    stop
}
```

Adjust source IP and path. Restrict UDP/TCP 514 to trusted forwarders only.

Register with Auth Insight:

```bash
ucr set authin/logs/extra=/var/log/authelia/auth.log
systemctl restart rsyslog
```

## Verify

Trigger a failed login on the SSO portal. On the UCS host:

```bash
tail -f /var/log/authelia/auth.log
grep -i username /var/log/authelia/auth.log
```

Then search **Auth Insight** in UMC for the same user.

## Security

- Syslog forward is **one-way** (docker host → UCS).
- Lines contain usernames and source IPs, not passwords.
- Restrict rsyslog source IPs; do not expose 514 to the internet.
