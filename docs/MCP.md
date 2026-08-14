# Heliox MCP interfaces

Heliox exposes two deliberately separate Model Context Protocol (MCP)
interfaces. They do not share credentials or authority.

## Public documentation MCP

`https://www.helioxos.dev/api/mcp` is a read-only Streamable HTTP endpoint for
documentation and evidence discovery. Its manifest is published at
`https://www.helioxos.dev/.well-known/mcp.json`.

It can search documentation, list published capabilities, explain action
safety, return the latest release and installation instructions, and report
current benchmark evidence. It cannot connect to a user's daemon or control a
computer.

## Local control MCP

`heliox-mcp` is a local stdio server installed with `pilot-daemon`. It connects
to the loopback Heliox daemon with a rotated, private MCP credential. Start the
desktop application before connecting an MCP host.

Use this generic MCP-host configuration:

```json
{
  "mcpServers": {
    "heliox-local": {
      "command": "heliox-mcp"
    }
  }
}
```

For a source checkout, replace the command with the Python environment in
which `daemon` was installed, or run `python -m pilot.mcp_server` from that
environment.

The server exposes seven tools:

| Tool | Effect |
| --- | --- |
| `heliox_health` | Check the daemon connection. |
| `get_heliox_system_status` | Read current daemon system status. |
| `list_heliox_capabilities` | List guarded Heliox actions and specialists. |
| `preview_heliox_task` | Create a non-binding, side-effect-free preview. |
| `submit_heliox_task` | Submit a task asynchronously to the guarded executor. |
| `get_heliox_task_status` | Poll durable task, approval, and terminal state. |
| `cancel_heliox_task` | Cancel an MCP-owned task. |

Submitting is not the same as completing. The tool returns a task identifier;
the host must poll `get_heliox_task_status` until the task reaches a terminal
state. A preview is advisory and submission replans against current state.

## Security boundary

- MCP has its own rotated runtime token and `mcp_local` RPC identity.
- The identity can call only the nine RPC methods needed by the seven tools.
- It cannot call raw `execute`, `confirm`, `update_config`, `store_api_key`, or
  arbitrary daemon methods.
- Every submitted action pauses for visible approval in the Heliox UI, even if
  the same action would normally auto-run for an interactive user.
- The MCP gateway profile denies arbitrary browser JavaScript, registry writes,
  and power shutdown/restart/logout, and it cannot request root authority.
- There is intentionally no MCP approval tool. A model or remote host cannot
  approve its own proposed effects.
- Task status and cancellation are restricted to MCP-owned durable tasks.
- The token remains in the per-user runtime directory and is never published
  by the public documentation MCP.

The MCP bridge therefore adds another client surface without creating another
execution authority: planning, policy, approval, execution, verification,
audit, cancellation, and durable recovery stay in the existing daemon path.
