import json
from pathlib import Path

paths = [
    "output/image/qwen3vl2b/batch_results.json",
    "output/video/qwen3vl2b/batch_results.json",
    "data/raw_memory/email/emails.json",
    "data/atm-bench/atm-bench.json",
]

for path in paths:
    print("=" * 100)
    print(path)

    p = Path(path)
    if not p.exists():
        print("File not found")
        continue

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("type:", type(data))

    if isinstance(data, list):
        print("length:", len(data))
        for i, item in enumerate(data[:2]):
            print(f"\n--- item {i} ---")
            print(json.dumps(item, ensure_ascii=False, indent=2)[:3000])

    elif isinstance(data, dict):
        print("keys:", list(data.keys())[:20])
        for i, (k, v) in enumerate(data.items()):
            print(f"\n--- key {k} ---")
            print(json.dumps(v, ensure_ascii=False, indent=2)[:3000])
            if i >= 1:
                break