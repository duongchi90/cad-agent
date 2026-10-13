import subprocess
import os
import json
import time

BINARY_PATH = r"C:\Tools\benchmarks\tier1\cadgeom_core.exe"
REA_SCRIPT = r"C:\Users\duong\AppData\Roaming\npm\node_modules\rea-agents\scripts\rea.mjs"
LOG_DIR = r"C:\Users\duong\ZCodeProject\cad-agent\research\antigravity\2026-10-13\rea_ghidra_maximum_capability\logs"

env = os.environ.copy()
env["JAVA_HOME"] = r"C:\Tools\jdk-21"
env["GHIDRA_INSTALL_DIR"] = r"C:\Tools\ghidra_12.1.4_PUBLIC"
env["REA_ANALYSIS_PROVIDER"] = "ghidra"
env["Path"] = r"C:\Tools\jdk-21\bin;" + env.get("Path", "")

def run_rea(args):
    cmd = ["node", REA_SCRIPT] + args + ["--provider", "ghidra", "--format", "json"]
    t0 = time.time()
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    elapsed = time.time() - t0
    if res.returncode != 0:
        print(f"Error running {' '.join(cmd)}: {res.stderr}")
        return None, elapsed
    try:
        return json.loads(res.stdout), elapsed
    except Exception as e:
        print(f"Failed to parse JSON: {e}\nRaw output: {res.stdout[:500]}")
        return res.stdout, elapsed

print("=== 1. REA INSPECT ===")
inspect_data, t_inspect = run_rea(["inspect", BINARY_PATH])
print(f"Inspect elapsed: {t_inspect:.2f}s")

print("=== 2. REA SEARCH PROCEDURES ===")
search_data, t_search = run_rea(["search", BINARY_PATH, "", "--kind", "procedures"])
print(f"Search elapsed: {t_search:.2f}s")

procedures = []
if isinstance(search_data, dict):
    raw = search_data.get("raw_result") or search_data.get("normalized_result") or []
    procedures = raw
print(f"Found {len(procedures)} procedures: {procedures}")

decompiled = {}
xrefs_map = {}

for proc in procedures:
    addr = proc if isinstance(proc, str) else proc.get("address", "")
    if not addr.startswith("0x"):
        addr = hex(int(addr)) if addr.isdigit() else addr
    print(f"Decompiling {addr}...")
    dec_data, t_dec = run_rea(["decompile", BINARY_PATH, addr])
    decompiled[addr] = {
        "data": dec_data,
        "elapsed": t_dec
    }
    
    print(f"Querying xrefs for {addr}...")
    xref_data, t_xr = run_rea(["xrefs", BINARY_PATH, addr])
    xrefs_map[addr] = {
        "data": xref_data,
        "elapsed": t_xr
    }

out_bundle = {
    "binary": BINARY_PATH,
    "inspect": inspect_data,
    "procedures": procedures,
    "decompiled": decompiled,
    "xrefs": xrefs_map,
    "timings": {
        "inspect": t_inspect,
        "search": t_search
    }
}

with open(os.path.join(LOG_DIR, "tier1_rea_raw.json"), "w", encoding="utf-8") as f:
    json.dump(out_bundle, f, indent=2)

print(f"Wrote full Tier 1 raw evidence to {os.path.join(LOG_DIR, 'tier1_rea_raw.json')}")
