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


def build_description_to_subcategory(event_pool):
    """
    构建一个映射表：
    event_description -> sub_category
    """
    desc_to_subcategory = {}

    for sub_category, info in event_pool.items():
        details = info.get("Detail", [])

        for desc in details:
            if desc in desc_to_subcategory:
                print(f"[Warning] duplicate description found:")
                print(desc)
                print(f"old: {desc_to_subcategory[desc]}, new: {sub_category}")

            desc_to_subcategory[desc] = sub_category

    return desc_to_subcategory


def add_sub_category(data, desc_to_subcategory):
    """
    遍历 data 中每个 primary_category 下的事件，
    根据 event_description 匹配 sub_category。
    """
    unmatched = []

    for primary_category, items in data.items():
        if not isinstance(items, list):
            continue

        for item in items:
            event_description = item.get("event_description")

            sub_category = desc_to_subcategory.get(event_description)

            if sub_category is not None:
                item["sub_category"] = sub_category
            else:
                item["sub_category"] = None
                unmatched.append({
                    "memory_id": item.get("memory_id"),
                    "primary_category": primary_category,
                    "event_description": event_description
                })

    return data, unmatched


event_pool_path = "output/event_classification/Event_pool.json"
data_path = "output/event_classification/sample_300_round2.json"
out_path = "output/event_classification/sample_300_round2_sub_category.json"
unmatched_path = "output/event_classification/sample_300_round2_unmatched_events.json"


event_pool = load_json(event_pool_path)
data = load_json(data_path)

desc_to_subcategory = build_description_to_subcategory(event_pool)

new_data, unmatched = add_sub_category(data, desc_to_subcategory)

save_json(new_data, out_path)
save_json(unmatched, unmatched_path)

print(f"Saved result to: {out_path}")
print(f"Unmatched count: {len(unmatched)}")
print(f"Saved unmatched events to: {unmatched_path}")