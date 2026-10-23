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

all_items = []

# image memories
image_data = load_json("output/image/qwen3vl2b/batch_results.json")
for item in image_data:
    memory_id = Path(item["image_path"]).stem

    text = f"""
Time: {item.get("timestamp", "")}
City: {item.get("city", "")}
Location: {item.get("location_name", "")}
Short caption: {item.get("short_caption", "")}
Caption: {item.get("caption", "")}
Tags: {", ".join(item.get("tags", []))}
Entities: {json.dumps(item.get("entities", []), ensure_ascii=False)}
OCR: {item.get("ocr_text", "")}
""".strip()

    all_items.append({
        "memory_id": memory_id,
        "modality": "image",
        "timestamp": item.get("timestamp", ""),
        "source_path": item.get("image_path", ""),
        "city": item.get("city", ""),
        "location_name": item.get("location_name", ""),
        "Short caption": item.get("short_caption", ""),
        "text_for_classification": text,
    })

# video memories
video_data = load_json("output/video/qwen3vl2b/batch_results.json")
for item in video_data:
    memory_id = Path(item["video_path"]).stem

    text = f"""
Time: {item.get("timestamp", "")}
City: {item.get("city", "")}
Location: {item.get("location_name", "")}
Duration: {item.get("duration_formatted", "")}
Short caption: {item.get("short_caption", "")}
Caption: {item.get("caption", "")}
Tags: {", ".join(item.get("tags", []))}
Entities: {json.dumps(item.get("entities", []), ensure_ascii=False)}
OCR: {item.get("ocr_text", "")}
""".strip()

    all_items.append({
        "memory_id": memory_id,
        "modality": "video",
        "timestamp": item.get("timestamp", ""),
        "source_path": item.get("video_path", ""),
        "city": item.get("city", ""),
        "location_name": item.get("location_name", ""),
        "Short caption" : item.get("short_caption", ""),
        "text_for_classification": text,
    })

# email memories
email_data = load_json("data/raw_memory/email/emails.json")
for item in email_data:
    text = f"""
Time: {item.get("timestamp", "")}
Summary: {item.get("short_summary", "")}
Detail: {item.get("detail", "")}
""".strip()

    all_items.append({
        "memory_id": item.get("id", ""),
        "modality": "email",
        "timestamp": item.get("timestamp", ""),
        "source_path": "",
        "city": "",
        "location_name": "",
        "Summary":item.get("short_summary", ""),
        "text_for_classification": text,
    })

imagecount = 0
emailcount = 0
videocount = 0

if isinstance(all_items,list):
    for item in all_items:
        if isinstance(item,dict):
            modality = item.get("modality","")

            if modality == "image":
                imagecount += 1
            elif modality =="email":
                emailcount += 1
            elif modality == "video":
                videocount += 1

print(f"imagecount = {imagecount}")
print(f"emailcount = {emailcount}")
print(f"videocount = {videocount}")

summary = {
    "ImageCount":imagecount,
    "EmailCount":emailcount,
    "VideoCount":videocount,
    "Total":imagecount+emailcount+videocount
}

all_items.insert(0,summary)


save_json(all_items, "output/event_classification/event_inputs.json")

print("Total items:", len(all_items))
print("Saved to output/event_classification/event_inputs.json")
#print(json.dumps(all_items[0], ensure_ascii=False, indent=2)[:2000])

# for event classification
# image：Short caption
# email：Summary
# video: Short caption
