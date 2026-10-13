import subprocess
import os
import json

BINARY_PATH = r"C:\Tools\ghidra_12.1.4_PUBLIC\docs\GhidraClass\ExerciseFiles\VersionTracking\WallaceVersion2.exe"
REA_SCRIPT = r"C:\Users\duong\AppData\Roaming\npm\node_modules\rea-agents\scripts\rea.mjs"
OUT_FILE = r"C:\Users\duong\ZCodeProject\cad-agent\research\antigravity\2026-10-13\rea_ghidra_true_blind_benchmark\logs\v2_decompiled.json"

env = os.environ.copy()
env["JAVA_HOME"] = r"C:\Tools\jdk-21"
env["GHIDRA_INSTALL_DIR"] = r"C:\Tools\ghidra_12.1.4_PUBLIC"
env["REA_ANALYSIS_PROVIDER"] = "ghidra"
env["Path"] = r"C:\Tools\jdk-21\bin;" + env.get("Path", "")

def run_rea(args):
    cmd = ["node", REA_SCRIPT] + args + ["--provider", "ghidra", "--format", "json"]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        print(f"Error running {' '.join(cmd)}: {res.stderr}")
        return None
    try:
        return json.loads(res.stdout)
    except Exception as e:
        print(f"JSON error: {e}")
        return None

# Find xrefs to "Wallace" in V2
s_res = run_rea(["search", BINARY_PATH, "Wallace", "--kind", "strings"])
wallace_addr = None
if s_res and "normalized_result" in s_res:
    for item in s_res["normalized_result"]:
        if item.get("value") == "Wallace":
            wallace_addr = item.get("address")
print(f"Wallace string in V2 at: {wallace_addr}")

# Query xrefs
xr_res = run_rea(["xrefs", BINARY_PATH, wallace_addr])
print(f"Xrefs in V2: {xr_res.get('normalized_result')}")

xrefs = xr_res.get("normalized_result") or []
v2_funcs = {}
for x in xrefs:
    print(f"Decompiling {x}...")
    dec = run_rea(["decompile", BINARY_PATH, x])
    v2_funcs[x] = dec.get("normalized_result")

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(v2_funcs, f, indent=2)

print("V2 analysis complete.")
