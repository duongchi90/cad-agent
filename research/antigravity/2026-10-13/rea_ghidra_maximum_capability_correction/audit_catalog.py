import re
import hashlib

catalog_path = r"research/antigravity/2026-10-11/REA_CATALOG.md"
with open(catalog_path, "rb") as f:
    content = f.read()

sha = hashlib.sha256(content).hexdigest()
text = content.decode("utf-8")

entries = re.findall(r"### (REA-\d{3}): ([^\n]+)", text)
print(f"TOTAL_ENTRIES={len(entries)}")

allowed_reuse = {
    "ALGORITHM_TRANSFER",
    "DEPENDENCY_REUSE",
    "CLEAN_ROOM_BEHAVIORAL_CONTRACT",
    "NEGATIVE_KNOWLEDGE",
    "RESEARCH_PRIOR_ONLY",
    "NOT_REUSABLE",
}
allowed_disposition = {
    "READY_TO_TRANSFER",
    "ALREADY_IMPLEMENTED",
    "RESEARCH_PRIOR",
    "REJECTED",
    "TRANSFER_EXPERIMENT_REQUIRED",
    "UNKNOWN",
}

invalid_reuse = 0
invalid_disposition = 0
multivalue_enum = 0

for m in re.finditer(r"- \*\*REUSE_CLASS:\*\* ([^\n]+)", text):
    raw = m.group(1).strip()
    val = re.sub(r"[^A-Z_]", "", raw)
    if "/" in raw or len(val.split()) > 1:
        multivalue_enum += 1
    if val not in allowed_reuse:
        print(f"Invalid reuse: {raw} -> {val}")
        invalid_reuse += 1

for m in re.finditer(r"- \*\*CURRENT_DISPOSITION:\*\* ([^\n]+)", text):
    raw = m.group(1).strip()
    val = re.sub(r"[^A-Z_]", "", raw)
    if "/" in raw or len(val.split()) > 1:
        multivalue_enum += 1
    if val not in allowed_disposition:
        print(f"Invalid disposition: {raw} -> {val}")
        invalid_disposition += 1

print(f"INVALID_REUSE_CLASS_COUNT={invalid_reuse}")
print(f"INVALID_DISPOSITION_COUNT={invalid_disposition}")
print(f"MULTIVALUE_ENUM_COUNT={multivalue_enum}")
print(f"CATALOG_SHA256={sha}")
