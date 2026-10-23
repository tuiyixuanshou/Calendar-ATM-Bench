import json
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def group_by_sub_category_without_primary(data):
    """
    去掉最外层 primary_category，
    直接按 sub_category 分组。

    原始事件顺序会保持不变。
    """
    grouped_data = {}

    for primary_category, items in data.items():
        if not isinstance(items, list):
            continue

        for item in items:
            sub_category = item.get("sub_category") or "unknown"

            if sub_category not in grouped_data:
                grouped_data[sub_category] = []

            grouped_data[sub_category].append(item)

    return grouped_data


data_path = "output/event_classification/sample_300_round2_sub_category.json"
out_path = "output/event_classification/sample_300_round3.json"

data = load_json(data_path)

grouped_data = group_by_sub_category_without_primary(data)

save_json(grouped_data, out_path)

print(f"Saved to {out_path}")