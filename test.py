import json
from datetime import datetime

path = "output/event_classification/sample_300_round2.json"

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def parse_timestamp(ts):
    """
    支持：
    2024-08-01 09:54:20
    2024-08-01 09:54:20+00:00
    """
    if not ts:
        return datetime.max

    # 去掉时区部分，例如 +00:00
    ts = ts.split("+")[0]

    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")

def sort_data_by_timestamp(items):
    return sorted(
        items,
        key=lambda item: parse_timestamp(item.get("timestamp"))
    )

data = load_json(path)

data["social"] = sort_data_by_timestamp(data.get("social", []))

save_json(data, path)