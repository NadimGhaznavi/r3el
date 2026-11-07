---
title: CMDB declarations and runtime configuration
author_profile: true
layout: single
lang: en
locale: en-US
language_name: English
translation_key: r3el-configuration
---

[Documentation index](../index.md)

R3el declares inventory metadata as literals in `r3el/constants/DR3el.py`.
CMDB reads this file without executing it. Register the application as `R3el`
and re-scan its production installation to discover its release and same-host
MariaDB catalog. CMDB does not yet collect network declarations; these describe
default listeners and already drive R3el's runtime defaults.

| Declaration | Purpose |
| --- | --- |
| `CMDB_DATABASES = (("R3el", "r3el"),)` | Names the local MariaDB catalog. Installation, upgrade checks, and removal look up the catalog by label. |
| `CMDB_NETWORK` use `http` | Control HTTP listener, default `0.0.0.0:42220`. |
| `CMDB_NETWORK` use `backend` | Batch server's ZeroMQ listener, default `127.0.0.1:42221`; also used by Control's batch client. |

Database references contain no credentials or remote connection settings.
`/etc/r3el/database.env` continues to supply runtime database credentials and
connection settings. MariaDB's outbound connection port and the independently
managed [LlamaSrv](https://llamasrv.osoyalce.com/) model service retain their own
configuration. Temporary ZeroMQ listeners used within a matching operation
continue to request an ephemeral port.

## Model connection

R3el defaults to `http://127.0.0.1:51001`, the inference endpoint provided by
[LlamaSrv](https://llamasrv.osoyalce.com/)
([GitHub repository](https://github.com/NadimGhaznavi/llamasrv)). LlamaSrv's
control panel uses port `51000`. These belong to LlamaSrv, so neither port is
part of R3el's `CMDB_NETWORK` or `conf/r3el.json` listener settings.

The installed R3el services use this default without additional configuration.
To connect to another host or a custom LlamaSrv inference port, set the base
URL in `/etc/r3el/server.env`, for example:

```ini
R3EL_LLM_URL=http://MODEL_HOST:51001
```

R3el appends `/v1/chat/completions`; omit that path and `/v1` from the base URL.
Install and upgrade preserve this file, including any old endpoint override.
After editing it, restart the affected R3el services when batch work can stop.
For a source checkout, export `R3EL_LLM_URL` or pass `--llm-url` to the batch
server. See [model setup and migration](one-batch-identification.md#llamasrv-model-service)
for LlamaSrv readiness and tool-calling requirements.

## Production listener overrides

The installer creates `/opt/prod/r3el/conf/r3el.json` from `CMDB_NETWORK` only
when missing, and preserves existing content during reinstall and upgrade.
The path follows `DR3el.BASE_DIR`. The file contains no secrets and is readable
by the service account. A missing file uses declaration defaults. For example:

```json
{
  "network": {
    "http": {"interface": "127.0.0.1", "port": 43220},
    "backend": {"port": 43221}
  }
}
```

Omitted listeners and fields inherit defaults. Only `network`, its declared uses,
and the `interface` and `port` fields are accepted. Interfaces must be IPv4 address
strings; ports must be integers from 1 to 65535. Invalid JSON or settings fail
with the path and setting identified. Invalid files never fall back to defaults.

`Configuration` resolves settings once per process; `Network.binding(use)` returns
the bind address and port. `Network.destination(use)` translates `0.0.0.0` to
`127.0.0.1` for local clients, retaining specific addresses. Control uses that
local destination when connecting to the batch server.

Control's `--host`, `--port`, and `--zmq-endpoint`, and the batch server's
`--zmq-endpoint`, override settings for that invocation. A manual endpoint override
must be supplied to both processes when they need to communicate.

## Apply changes

Edit the production JSON file, then run:

```sh
/opt/prod/r3el/scripts/services.sh restart
```

This validates the settings before stopping either R3el service, then starts
Control and the batch server with the new settings. Restart stops active batch
work; use it when the batch server can be stopped. LlamaSrv's inference service must
already be ready before batch work starts. `services.sh start` also validates
configuration before service actions. Installation and upgrade validate before
stopping services; they start Control and leave the batch service stopped.

Changing runtime overrides does not change CMDB's declared default inventory.
