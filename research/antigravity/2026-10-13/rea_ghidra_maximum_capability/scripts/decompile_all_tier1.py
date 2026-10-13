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

procedures = [
    "0x140001000",
    "0x140001050",
    "0x140001390",
    "0x1400013d0",
    "0x1400013f0",
    "0x140001520",
    "0x140001710",
    "0x140001790",
    "0x140001a40",
    "0x140001bc0",
    "0x140001c50",
    "0x140001c80"
]

results = {}

for addr in procedures:
    print(f"=== Decompiling {addr} ===")
    cmd_dec = ["node", REA_SCRIPT, "decompile", BINARY_PATH, addr, "--provider", "ghidra", "--format", "json"]
    t0 = time.time()
    res_dec = subprocess.run(cmd_dec, env=env, capture_output=True, text=True, timeout=120)
    t_dec = time.time() - t0
    
    dec_obj = {}
    if res_dec.returncode == 0:
        try:
            dec_obj = json.loads(res_dec.stdout)
        except Exception as e:
            dec_obj = {"error": str(e), "raw": res_dec.stdout}
    else:
        dec_obj = {"error": res_dec.stderr}

    print(f"=== Xrefs for {addr} ===")
    cmd_xr = ["node", REA_SCRIPT, "xrefs", BINARY_PATH, addr, "--provider", "ghidra", "--format", "json"]
    t0 = time.time()
    res_xr = subprocess.run(cmd_xr, env=env, capture_output=True, text=True, timeout=120)
    t_xr = time.time() - t0
    
    xr_obj = {}
    if res_xr.returncode == 0:
        try:
            xr_obj = json.loads(res_xr.stdout)
        except Exception as e:
            xr_obj = {"error": str(e), "raw": res_xr.stdout}
    else:
        xr_obj = {"error": res_xr.stderr}

    results[addr] = {
        "pseudocode": dec_obj.get("normalized_result") or dec_obj.get("raw_result"),
        "xrefs": xr_obj.get("normalized_result") or xr_obj.get("raw_result"),
        "decompile_latency_sec": round(t_dec, 2),
        "xrefs_latency_sec": round(t_xr, 2)
    }

out_path = os.path.join(LOG_DIR, "tier1_decompiled.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"Successfully saved all 12 decompiled procedures to {out_path}")
