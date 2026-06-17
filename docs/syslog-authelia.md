# Forward Authelia auth logs to beach (syslog)

Authelia on **douglas** writes structured login failures to container logs.
Auth Insight on **beach** reads local files. Forward Authelia events via syslog
so the UMC module stays responsive (no SSH/docker exec from beach).

## Recommended layout

```text
douglas (Authelia docker) → rsyslog → beach:/var/log/authelia/auth.log
                                      → authin via UCR authin/logs/extra
```

## douglas — Authelia → syslog

1. Configure Authelia file or stdout logging (default docker logs is fine).
2. Add **promtail**, **fluent-bit**, or **rsyslog** imfile on the docker log path, **or**
   set Authelia `log_file_path` to a host-mounted volume.

Example **rsyslog** forwarder on douglas (`/etc/rsyslog.d/authelia-forward.conf`):

```rsyslog
# Authelia container logs tagged by docker logging driver, or file:
input(type="imfile"
      File="/var/lib/docker/containers/*/*-json.log"
      Tag="authelia"
      readMode="2")

if $programname == 'authelia' then @@beach.in.ecotegral.com:514
& stop
```

Use a dedicated tag/filter so only Authelia lines are forwarded.

## beach — receive and store

`/etc/rsyslog.d/authelia-remote.conf`:

```rsyslog
module(load="imudp")
input(type="imudp" port="514")

if $fromhost-ip == '10.64.30.11' and $programname == 'authelia' then {
    action(type="omfile" file="/var/log/authelia/auth.log")
    stop
}
```

Adjust douglas IP and path. Restrict UDP/TCP 514 to douglas only on the firewall.

Register with Auth Insight:

```bash
ucr set authin/logs/extra=/var/log/authelia/auth.log
systemctl restart rsyslog
```

## Verify

On douglas, trigger a failed login. On beach:

```bash
tail -f /var/log/authelia/auth.log
grep -i gustavom /var/log/authelia/auth.log
```

Then search **Auth Insight** in UMC for the same user.

## Security

- Syslog forward is **one-way** (douglas → beach).
- Lines contain usernames and source IPs, not passwords.
- Restrict rsyslog source IPs; do not expose 514 to the internet.
