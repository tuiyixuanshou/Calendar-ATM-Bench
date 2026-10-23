import json
import re
from pathlib import Path
from typing import Any

import LLM_interface


EVENT_GENERATION_SYSTEM_PROMPT = """
你是一个虚拟角色的生活轨迹叙事生成器。

你会收到一条轨迹记录。轨迹中的原始事件可能来自用户的图片、视频或邮件，
但你需要将其改写为虚拟角色亲身经历或参与过的生活事件。

你的任务包括：

1. 从 behavior_apply_detail 中提取实际发生的核心事件。
2. 使用第一人称“我”来描述这件事。
3. 结合以下状态进行适当发挥：
   - 体力值
   - 情绪效价
   - 情绪唤醒程度
   - 行为结果
4. 描述应当像虚拟角色对自己一天经历的自然回忆，而不是数据分析报告。
5. 不要出现“图片显示”“视频中”“邮件中提到”“根据记录”等表达。
6. 不要直接输出体力值、情绪数值、score 或 behavior_name。
7. 可以根据状态补充合理的感受、过程和结果，但不要改变核心事件。
8. 如果原始事件是邮件提醒，应改写成角色收到了提醒、查看了信息或为对应事项做准备。
9. 如果原始事件只是看到某个物品或场景，可以描述成角色前往现场、观察、欣赏或短暂停留。
10. 最终只生成一段中文描述，长度控制在80至160字，不要输出标题、列表或解释。

行为结果可以参考以下含义：

- 实现目标：事情顺利完成，角色获得明显满足感。
- 进展顺利：过程较为顺利，虽然不一定完全结束，但有积极进展。
- 小有收获：得到了一些体验、信息或情绪上的收获。
- 情况不妙：过程出现明显问题，但尚未完全失败。
- 惨遭失败：目标没有实现，角色可能感到失望、疲惫或不安。

情绪效价描述角色当前的愉悦程度。
情绪唤醒描述角色当前的兴奋、活跃或紧张程度。
体力值越低，描述中越可以体现疲惫、行动迟缓或需要休息。
"""


def load_json(path: str) -> Any:
    """读取 JSON 文件。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, path: str) -> None:
    """保存 JSON 文件，并自动创建父目录。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_item_value(item: dict, possible_keys: list[str], default=None):
    for key in possible_keys:
        if key in item:
            return item[key]

    # 再进行一次去除首尾空格后的匹配
    normalized_keys = {
        str(key).strip(): value
        for key, value in item.items()
    }

    for key in possible_keys:
        normalized_key = key.strip()
        if normalized_key in normalized_keys:
            return normalized_keys[normalized_key]

    return default


def build_event_prompt(item: dict) -> str:
    energy = get_item_value(
        item,
        ["🔋 体力值: ", "🔋 体力值:"],
        default=0.5
    )

    emotion_valence = get_item_value(
        item,
        ["🔋 情绪效价: ", "🔋 情绪效价:"],
        default="普通(0.00)"
    )

    emotion_arousal = get_item_value(
        item,
        ["🔋 情绪唤醒:", "🔋 情绪唤醒: "],
        default="正常(0.00)"
    )

    behavior_name = item.get("behavior_name", "")
    behavior_detail = item.get("behavior_apply_detail", "")
    behavior_result = item.get("behavior_result", "")
    score = item.get("score", 0.0)

    return f"""
请将下面这条轨迹改写为虚拟角色的第一人称生活经历。

轨迹信息：

行为类别：
{behavior_name}

原始事件：
{behavior_detail}

行为结果：
{behavior_result}

当前体力值：
{energy}

当前情绪效价：
{emotion_valence}

当前情绪唤醒：
{emotion_arousal}

行为匹配分数：
{score}

请从原始事件中提取核心活动，并结合角色状态生成一段自然、连贯的中文叙述。
只输出最终的第一人称事件描述。
""".strip()


def clean_llm_response(response: Any) -> str:
    """
    清理 LLM 返回结果。

    兼容：
    1. 直接返回字符串
    2. 返回字典
    3. 返回带 Markdown 代码块的文本
    """

    if response is None:
        return ""

    if isinstance(response, dict):
        # 根据不同接口的返回结构按需扩展
        if "content" in response:
            text = response["content"]
        elif "response" in response:
            text = response["response"]
        elif "text" in response:
            text = response["text"]
        else:
            text = json.dumps(response, ensure_ascii=False)
    else:
        text = str(response)

    text = text.strip()

    # 去除 ```text ... ``` 或 ``` ... ```
    text = re.sub(
        r"^```(?:json|text|markdown)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(r"\s*```$", "", text)

    # 去除一些模型可能添加的字段前缀
    prefixes = [
        "事件描述：",
        "生成结果：",
        "第一人称描述：",
        "描述："
    ]

    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    return text


def generate_event_description(
    item: dict,
    llm_interface
) -> str:
    """调用 LLM，为一条轨迹生成第一人称事件描述。"""

    user_prompt = build_event_prompt(item)

    res = [
        {
            "role": "system",
            "content": EVENT_GENERATION_SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": user_prompt
        }
    ]

    response = llm_interface.dialog(res)
    return clean_llm_response(response)


def process_trajectory(
    input_path: str,
    output_path: str,
    llm_interface
) -> list[dict]:
    """处理完整轨迹文件。"""

    trajectory = load_json(input_path)

    if not isinstance(trajectory, list):
        raise ValueError("输入文件的最外层必须是 JSON 列表。")

    generated_trajectory = []

    total = len(trajectory)

    for index, item in enumerate(trajectory):
        if not isinstance(item, dict):
            print(f"[跳过] 第 {index + 1} 条数据不是字典。")
            continue

        print(f"[{index + 1}/{total}] 正在生成事件描述……")

        new_item = item.copy()

        try:
            generated_text = generate_event_description(
                item=item,
                llm_interface=llm_interface
            )

            new_item["generated_event_description"] = generated_text
            new_item["generation_status"] = "success"

            print(generated_text)

        except Exception as error:
            new_item["generated_event_description"] = ""
            new_item["generation_status"] = "failed"
            new_item["generation_error"] = str(error)

            print(f"[生成失败] 第 {index + 1} 条：{error}")

        generated_trajectory.append(new_item)

        # 每处理一条就保存，避免程序中途退出导致全部结果丢失
        save_json(generated_trajectory, output_path)

    print(f"\n处理完成，结果已保存至：{output_path}")
    return generated_trajectory


if __name__ == "__main__":
    input_path = "output/atm_action/ActionList2.json"
    output_path = "output/atm_action/ActionList2_generated.json"

    llm_interface = LLM_interface.LLM_interface_Azure(
        deployment="gpt-4.1_2025-04-14",
        api_version="2025-04-01-preview",
        isTRAPI=True
    )

    process_trajectory(
        input_path=input_path,
        output_path=output_path,
        llm_interface=llm_interface
    )