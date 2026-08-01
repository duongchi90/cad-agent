# `dotnet_ipc`

`dotnet_ipc` is the bounded Python client for the AutoCAD Managed .NET File
IPC contract. It is deliberately separate from the existing
`autocad_mcp_*` dispatcher files.

```python
from dotnet_ipc import DotNetIPCClient

client = DotNetIPCClient(trigger=trigger_cadagent_dispatch)
health = client.health()
review = client.review(r"C:\temp\sample.dwg", ["10", "A0"])
client.close_disposable(r"C:\temp\sample.dwg")
```

The injected trigger takes no arguments. It should invoke the loaded
`CADAGENT_DISPATCH` command after the request file is written. The request and
result files are:

```text
<ipc_dir>/cadagent_dotnet_request_<request_id>.json
<ipc_dir>/cadagent_dotnet_result_<request_id>.json
```

The default IPC directory is `C:\temp`; `CAD_AGENT_DOTNET_IPC_DIR` overrides
it. JSON is encoded as UTF-8 and written through a same-directory temporary
file followed by an atomic replace. Reads are bounded to 1 MiB by default,
polling uses a monotonic deadline, and every operation removes only its own
request/result pair in a `finally` block. A result must preserve the request id
and operation, and a `success=false` result raises `DotNetIPCResultError`.

`close_disposable` always requires `disposable=True` and
`save_changes=False`; the client never sends a save request. The legacy
`autocad_mcp_*` files are not read or removed by this package.
