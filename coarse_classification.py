import LLM_interface
import json
import random
from collections import defaultdict
from pathlib import Path

from concurrent.futures import ThreadPoolExecutor, as_completed

import time

random.seed(42)


COARSE_CLASSIFICATION_PROMPT = """You are an event classifier. You will receive one real human activity memory. The modality may be image, email, or video. Each memory provides a short description. First, understand the “main activity event” expressed in the memory description, and then classify it into one of five high-level event categories.

Please make the judgment in the following steps:

Step 1: Identify the main activity event
First answer: What is the core activity, event, or matter expressed in this memory description?

You may extract the main event expressed in the memory, or the main activity that is recorded or observed. If there is an activity subject and an activity scene, you may also extract them as supporting information for the main event. Note: If no main activity event can be extracted from this memory, please respond: "no event"

Step 2: Classify the event into five high-level categories

If a main activity event is identified in Step 1, classify the event into one of the following five high-level categories:

physiological
Related to bodily needs, eating, sleeping, health, exercise, rest, or physical condition.
Examples: eating, drinking water, sleeping, feeling unwell, seeing a doctor, exercising, fatigue, recovery.
work
Related to study, research, occupation, tasks, meetings, courses, papers, projects, tools, productivity, or technical information.
Examples: course notifications, meeting arrangements, paper-related matters, project updates, work emails, technical newsletters, webinars.
leisure
Related to entertainment, travel, sightseeing, walking, nature observation, hobbies, consumption, music, games, exhibitions, or everyday relaxation.
Examples: looking at the sea, taking landscape photos, visiting a castle, listening to music, buying vinyl records, walking, watching animals, travel photos.
social
Related to interpersonal interaction, gatherings, shared activities, appointments to meet, multiple-person participation, or relationship maintenance.
Examples: restaurant reservations for two people, meals with friends, walking together, group activities, communicating with others, social invitations.
emotional
Related to emotional expression, close relationships, care, loneliness, commemoration, support, comfort, or strong personal feelings.
Examples: expressing missing someone, receiving comfort, anniversaries, emotional support, pet companionship, expressing gratitude, sad or happy emotional events.

If main_event is "no event", then primary_category and secondary_categories may be empty

Please output JSON only. The output format should be:

{
"main_event": "A summary of the main event",
"primary_category": "One of physiological, work, leisure, social, emotional or no event",
"secondary_categories": [can be None]
}

Now classify the following memory/event:

modality: <modality>

description: <event_description>"""



LEVEL_PROMPT = """You are an event classifier. I will provide you with a set of event data where primary_category = <primary_category>. Based on these data, summarize more detailed subcategories for these social events.
Requirements:
Do not create overly specific categories for single special cases. The categories should be as mutually exclusive as possible. The summarized categories should cover as many event records as possible.
input data:<input data>
Please output JSON only. The output format should be:
["category1","category2","category3",...]
"""


MERGE_TAXONOMY_PROMPT = """You are an event taxonomy designer.

I will provide multiple candidate taxonomies generated from different batches of <primary_category> event data.

Your task is to merge them into one final taxonomy for `primary_category = <primary_category>`.

Requirements:
1. Merge duplicate or semantically similar categories.
2. The final categories should be mutually exclusive as much as possible.
3. Each final category should be reusable across multiple event records.
4. Keep the taxonomy concise and stable.
5. Return valid JSON only.

Output format:
{
  "primary_category": "social",
  "subcategories": [
    {
      "label": "conference_expo_trade_show",
      "merged_from": ["Conferences, Expos & Trade Shows"]
    },
  ]
}

Candidate taxonomies:
<input taxonomies>
"""

CLASSIFY_PROMPT = """You are an event classifier. You will receive a piece of event data, which may come from an image, an email, a video, or a text description. Your task is to understand the core activity described in the event and classify it into the given fixed taxonomy.

Please note: You must not create any new primary categories or subcategories. You may only choose the most appropriate category from the taxonomy provided below.
event_type：
<event_keys_text>

event：<event>

Return valid JSON only. Output format:
{"event_type"："chosen event categories"}

"""


def save(data,path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def bulid_prompt(item):
    return (
        COARSE_CLASSIFICATION_PROMPT
        .replace("<modality>",item.get("modality"))
        .replace("<event_description>",item.get("event_description"))
    )

def normalize_text(x):
    return str(x or "").strip().lower()

def classify_one(index, item, llm_interface):
    prompt = build_classify_prompt(item,event_keys_text)

    Prompt = [{
        "role":"user",
        "content":prompt
    }]

    res = llm_interface.dialog(Prompt)
    llm_res = json.loads(res)

    main_event = llm_res.get("main_event").strip().lower()
    primary_category = llm_res.get("primary_category").strip().lower()
    secondary_categories = llm_res.get("secondary_categories")

    main_event = normalize_text(llm_res.get("main_event"))
    primary_category = normalize_text(llm_res.get("primary_category"))
    secondary_categories = llm_res.get("secondary_categories", [])

    return {
        "index": index,
        "main_event": main_event,
        "primary_category": primary_category,
        "secondary_categories": secondary_categories,
    }

def classify_finally(index, item, llm_interface):
    prompt = build_classify_prompt(item,event_keys_text)

    Prompt = [{
        "role":"user",
        "content":prompt
    }]

    res = llm_interface.dialog(Prompt)
    llm_res = json.loads(res)

    event_type = llm_res.get("event_type").strip()

    return {
        "index": index,
        "event_type":event_type
    }

def update_count(summary, primary_category):
    if "physiological" in primary_category:
        summary["physiologicalCount"] += 1
    elif "work" in primary_category:
        summary["workCount"] += 1
    elif "leisure" in primary_category:
        summary["leisureCount"] += 1
    elif "social" in primary_category:
        summary["socialCount"] += 1
    elif "emotional" in primary_category:
        summary["emotionalCount"] += 1
    else:
        summary["no_eventCount"] += 1

def load_json(path):
    with open(path,"r",encoding = "utf-8") as f:
        data = json.load(f)

    return data

data_path = "output/event_classification/event_inputs.json"
sample_path = "output/event_classification/sample_300.json"
out_path = "output/event_classification/sample_300_round1.json"

round2_path = "output/event_classification/sample_300_round2.json"


category = "leisure"
batch_level = f"output/event_classification/{category}.json"
final_taxonomy_path =f"output/event_classification/final_{category}.json"

event_path =f"Event_pool.json"
event_out_path = f"output/event_classification/Event_pool.json.json"
events = load_json(event_path)
data = load_json(sample_path)

event_keys = list(events.keys())
event_keys_text = json.dumps(event_keys, ensure_ascii=False, indent=2)

def build_classify_prompt(item,event_keys_text):
    event_text = item.get("Short caption") or item.get("Summary") or ""

    return (
        CLASSIFY_PROMPT
        .replace("<event>", event_text)
        .replace("<event_keys_text>", event_keys_text)
    )

llm_interface = LLM_interface.LLM_interface_Azure(
    deployment="gpt-4.1_2025-04-14",
    api_version="2025-04-01-preview",
    isTRAPI=True
)

max_workers =5
completed = 0

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    future_to_index = {
        executor.submit(classify_finally,i,item,llm_interface):i
        for i,item in enumerate(data)
    }

    for future in as_completed(future_to_index):
        i = future_to_index[future]

        try:
            result = future.result()
            idx = result["index"]
            item = data[idx]

            event_type = result["event_type"]
            event_text = item.get("Short caption") or item.get("Summary") or ""
            if events.get(event_type,"") == "":
                print("未知 event_type:", result)

            else:
                events[event_type].setdefault("Detail", []).append(event_text)

            completed += 1

            if completed %15 == 0:
                save(events,event_out_path)
                print(f"已完成 {completed}/{len(data)}，已保存")

        except Exception as e:
            print(f"第{i}条处理失败")


# data = load_json(round2_path)

# social_data = data[category]


# def make_batches(items, batch_size=20):
#     batches = []

#     for i in range(0, len(items), batch_size):
#         batch = items[i:i + batch_size]
#         batches.append(batch)

#     return batches

# def process_batch(batch_idx, batch, llm_interface):
#     input_events = []

#     for item in batch:
#         input_events.append({
#             "event_description": item.get("event_description"),
#         })

#     events_text = json.dumps(input_events, ensure_ascii=False, indent=2)
#     prompt = LEVEL_PROMPT.replace("<input data>", events_text).replace("<primary_category>",category)

#     messages = [
#         {
#             "role": "user",
#             "content": prompt
#         }
#     ]

#     res = llm_interface.dialog(messages)
#     llm_res = json.loads(res)

#     return {
#         "batch_idx": batch_idx,
#         "taxonomy": llm_res
#     }
    
# llm_interface = LLM_interface.LLM_interface_Azure(
#     deployment="gpt-4.1_2025-04-14",
#     api_version="2025-04-01-preview",
#     isTRAPI=True
# )

# batches = make_batches(social_data, batch_size=15)

# batch_taxonomies = []

# with ThreadPoolExecutor(max_workers=5) as executor:
#     future_to_batch_idx = {}

#     for batch_idx, batch in enumerate(batches):
#         future = executor.submit(process_batch, batch_idx, batch,llm_interface)
#         future_to_batch_idx[future] = batch_idx

#     for future in as_completed(future_to_batch_idx):
#         batch_idx = future_to_batch_idx[future]

#         try:
#             result = future.result()
#             batch_taxonomies.append(result)

#             print(f"✅ batch {batch_idx} done")

#             save(batch_taxonomies,batch_level)

#         except Exception as e:
#             print(f"❌ batch {batch_idx} failed: {e}")


# batch_taxonomies = sorted(
#     batch_taxonomies,
#     key=lambda x: x["batch_idx"]
# )

# save(batch_taxonomies, batch_level)

# print("All done.")

# taxonomy_text = json.dumps(batch_taxonomies, ensure_ascii=False, indent=2)

# merge_prompt = (MERGE_TAXONOMY_PROMPT.replace(
#     "<input taxonomies>",
#     taxonomy_text
# )
# .replace("<primary_category>",category))

# messages = [{"role": "user", "content": merge_prompt}]

# res = llm_interface.dialog(messages)
# print(res)
# final_taxonomy = json.loads(res)

# save(final_taxonomy, final_taxonomy_path)

# print(final_taxonomy)


# data = load_json(out_path)

# by_category = defaultdict(list)
# for i,item in enumerate(data):
#     if i == 0: continue
#     if item.get("primary_category","") == "":
#         print(f"第{i}条无primary_category字段，id：{item.get("memory_id")}")
#     by_category[item["primary_category"]].append(item)

# save(by_category,"output/event_classification/sample_300_round2.json")


# with open(out_path,"r",encoding="utf-8") as f:
#     data = json.load(f)


# Summary = {
#     "physiologicalCount" : 0,
#     "workCount" : 0,
#     "leisureCount" : 0,
#     "socialCount" : 0,
#     "emotionalCount" : 0,
#     "no_eventCount" : 0,
# }

# if len(data) == 0:
#     raise ValueError("data is empty")

# if data[0].get("modality","") != "":
#     data.insert(0, Summary)
#     save(data,out_path)

# summary = data[0]

# llm_interface = LLM_interface.LLM_interface_Azure(
#     deployment="gpt-5.5_2026-04-24",
#     api_version="2025-04-01-preview",
#     isTRAPI=True
# )

# tasks = []

# for i,item in enumerate(data):
#     if i == 0:
#         continue

#     if item.get("main_event","")  != "":
#         continue

#     tasks.append((i,item))

# print(f"待处理数量: {len(tasks)}")

# max_workers = 5
# completed = 0

# with ThreadPoolExecutor(max_workers=max_workers) as executor:
#     future_to_index = {
#         executor.submit(classify_one,i,item,llm_interface):i
#         for i,item in tasks
#     }

#     for future in as_completed(future_to_index):
#         i = future_to_index(future)

#         try:
#             result = future.result()
#             idx = result["index"]
#             item = data[idx]

#             item["main_event"] = result["main_event"]
#             item["primary_category"] = result["primary_category"]
#             if result["secondary_categories"] != []:
#                 item["secondary_categories"] = result["secondary_categories"]

#             update_count(summary, result["primary_category"])
#             completed += 1

#             if completed %10 == 0:
#                 data[0] = summary
#                 save(data,out_path)
#                 print(f"已完成 {completed}/{len(tasks)}，已保存")

#         except Exception as e:
#             print(f"第{i}条处理失败")


# data[0] = Summary
# save(data,out_path)


    



# with open(sample_path,"r",encoding="utf-8") as f:
#     data = json.load(f)

# classification_Data = []

# for i,item in enumerate(data):
#     if i == 0:
#         continue
#     modality = item.get("modality")
#     if modality =="email":
#         event_description = item.get("Summary")
#     else:
#         event_description = item.get("Short caption")

#     llmitem = {
#         "memory_id":item.get("memory_id"),
#         "timestamp": item.get("timestamp"),
#         "modality":modality,
#         "event_description":event_description
#     }

#     classification_Data.append(llmitem) # 需要进行分类的item

# save(classification_Data,out_path)



# with open(data_path,"r",encoding="utf-8") as f:
#     data = json.load(f)

# by_modality = defaultdict(list)
# for i,item in enumerate(data):
#     if i == 0:
#         continue
#     by_modality[item["modality"]].append(item)

# # 抽样样本
# sample_config = {
#     "image": 100,
#     "email": 100,
#     "video": 100
# }

# sampled = []
# sampled.append(sample_config)


# for modality, n in sample_config.items(): 
#     items = by_modality[modality] 
#     sampled.extend(random.sample(items, min(n, len(items)))) 

# save(sampled,out_path)