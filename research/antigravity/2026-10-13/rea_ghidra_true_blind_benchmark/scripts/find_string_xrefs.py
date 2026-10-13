import subprocess
import os
import json

BINARY_PATH = r"C:\Tools\ghidra_12.1.4_PUBLIC\docs\GhidraClass\ExerciseFiles\VersionTracking\WallaceSrc.exe"
REA_SCRIPT = r"C:\Users\duong\AppData\Roaming\npm\node_modules\rea-agents\scripts\rea.mjs"

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
        print(f"JSON error: {e}\n{res.stdout[:500]}")
        return None

target_strings = ["0x416830", "0x416860", "0x41687c", "0x4168c0"]

for s_addr in target_strings:
    print(f"Querying xrefs for {s_addr}...")
    res = run_rea(["xrefs", BINARY_PATH, s_addr])
    print(f"Xrefs for {s_addr}:")
    print(json.dumps(res, indent=2))
