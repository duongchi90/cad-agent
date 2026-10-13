import subprocess
import os
import json

BINARY_PATH = r"C:\Tools\ghidra_12.1.4_PUBLIC\docs\GhidraClass\ExerciseFiles\VersionTracking\WallaceSrc.exe"
REA_SCRIPT = r"C:\Users\duong\AppData\Roaming\npm\node_modules\rea-agents\scripts\rea.mjs"
OUT_FILE = r"C:\Users\duong\ZCodeProject\cad-agent\research\antigravity\2026-10-13\rea_ghidra_true_blind_benchmark\logs\app_decompiled.json"

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

funcs = ["0x4117c0", "0x411860", "0x4118f0", "0x41194d"]
results = {}

for addr in funcs:
    print(f"Decompiling {addr}...")
    res = run_rea(["decompile", BINARY_PATH, addr])
    if res and "normalized_result" in res:
        results[addr] = res["normalized_result"]
    elif res and "raw_result" in res:
        results[addr] = res["raw_result"]
    else:
        results[addr] = res

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("Saved all decompiled functions.")
