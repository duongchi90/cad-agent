import subprocess
import os
import json
import time

BINARY_PATH = r"C:\Tools\ghidra_12.1.4_PUBLIC\docs\GhidraClass\ExerciseFiles\VersionTracking\WallaceSrc.exe"
REA_SCRIPT = r"C:\Users\duong\AppData\Roaming\npm\node_modules\rea-agents\scripts\rea.mjs"
LOG_DIR = r"C:\Users\duong\ZCodeProject\cad-agent\research\antigravity\2026-10-13\rea_ghidra_true_blind_benchmark\logs"

env = os.environ.copy()
env["JAVA_HOME"] = r"C:\Tools\jdk-21"
env["GHIDRA_INSTALL_DIR"] = r"C:\Tools\ghidra_12.1.4_PUBLIC"
env["REA_ANALYSIS_PROVIDER"] = "ghidra"
env["Path"] = r"C:\Tools\jdk-21\bin;" + env.get("Path", "")

def run_rea(args):
    cmd = ["node", REA_SCRIPT] + args + ["--provider", "ghidra", "--format", "json"]
    t0 = time.time()
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=180)
    elapsed = time.time() - t0
    if res.returncode != 0:
        print(f"Error running {' '.join(cmd)}: {res.stderr}")
        return None, elapsed
    try:
        return json.loads(res.stdout), elapsed
    except Exception as e:
        print(f"Failed to parse JSON: {e}\nRaw output: {res.stdout[:500]}")
        return res.stdout, elapsed

print("=== 1. SEARCH STRINGS ===")
strings_data, t_str = run_rea(["search", BINARY_PATH, "", "--kind", "strings"])
print(f"Strings search elapsed: {t_str:.2f}s")

with open(os.path.join(LOG_DIR, "blind_strings.json"), "w", encoding="utf-8") as f:
    json.dump(strings_data, f, indent=2)

print("=== 2. SEARCH PROCEDURES ===")
procs_data, t_proc = run_rea(["search", BINARY_PATH, "", "--kind", "procedures"])
print(f"Procedures search elapsed: {t_proc:.2f}s")

with open(os.path.join(LOG_DIR, "blind_procedures.json"), "w", encoding="utf-8") as f:
    json.dump(procs_data, f, indent=2)

print("Done collecting strings and procedures.")
