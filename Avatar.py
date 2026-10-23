import random
import re
import numpy as np
from datetime import datetime, timedelta, time
import json

import Emotion
#import Memory
import Calendar
import LLM_interface
from json_repair import repair_json



class VirtualAgent:
    def __init__(self, personality, emotional_vector, behavior_library, 
                 favourite_L1_embedding = None, favourite_L2_embedding = None, favourite_L3_embedding = None, 
                 username = None,agent_name = None, policy_config=None):
        #print("\n\n\n\n\n")
        print(f"\n🤖 Avatar创建-----------------")
        #print("个性数值:" + str(personality))
        #print("情绪数值:" + str(emotional_vector))

        self.agent_name = agent_name

        self.user_gender = ""
        self.user_nick_name = ""
        self.user_basic_info = ""
        self.user_birthday = ""
        self.username = None
        self.user_familiar = 0.0
        self.user_safety = 1.0
        self.user_setting_xiaobai = "" #用户设置的小白属性
        self.user_setting_dialect = "" #用户设置的小白方言
        self.Image_read = 0
        self.model_name = "openai"  # 原定model_name ,model_name为None，就会根据using_deep_seek来决定是使用openai还是ds
        # self.model_name = "deepseek"  # 1029测试使用

        self.location = "北京"
        self.personality = personality
        self.bps_state_vector = personality # BPS需求向量
        self.behavior_library = behavior_library       
        self.luck = 0.8 # 幸运值
        self.bio_energy = 1.0 # 体力 
        self.behavior_fatigue = {}  # 记录每个行为的倦怠值 ∈ [0, 1]

        self.emotion_module = Emotion.EmotionState(personality,emotional_vector) # 添加情绪模块
        # self.dialogue_module = Dialog.DialogModule(self) # 添加对话模块
        # self.summary_module = Summary.SummaryModule(self) # 添加对话模块
        # self.memory_module = Memory.MemoryModule(self,50) # 添加记忆模块
        # self.external_event_manager = World_Plan.ExternalEventManager("M_file/External_Event.json")

        # 面向user的agent实例
        if self.username == None:
            self.calendar_module = Calendar.Calendar( # 添加无姓名日历模块，即公共小白
                self,days = 5,
                is_main_server=True) # False表示非主服务器，只会拉取git中的Calendar。   True表示为主服务器，会生成日历新内容

        #self.detector = SensitiveDetector()

        # 这里的问题
        #self.DIALOG_DEEP_SEEK = True
        self.DIALOG_DEEP_SEEK = False # 初始化的原因

        self.cur_behavior_library = []   # 需要重新设定

        self.timestamp = None
        self.atm_action_list = []

        #self.hotContent = HotContentMatcher.HotContentMatcher(self)

        #print(self.user_nick_name)

    

    def user_familiar_incresing(self):
        print(f"user_familiar_incresing:{self.user_familiar}")
        self.user_familiar += 0.01
        self.user_familiar = min(1.0,self.user_familiar)

    def reset_state(self): # 重置Agent状态 最开始的Agent就是从这个状态开始的
        self.bio_energy = 1.0 # 体力
        self.luck = 0.5
        self.emotion_module.valence = self.emotion_module.valence_baseline  # 让情绪回到偏向值
        self.emotion_module.arousal = 0.5
        self.emotion_module.frustration_level = 0.0
        self.emotion_module.mood_history = []
        self.behavior_fatigue = {}
    
    def restore_state(self,user_state):
        self.user_gender = user_state.user_gender
        self.user_nick_name = user_state.user_nickname
        self.user_basic_info = user_state.user_basic_info
        self.user_birthday = user_state.user_birthday
        self.user_familiar = user_state.user_familiar
        self.DIALOG_DEEP_SEEK = user_state.DIALOG_DEEP_SEEK
        self.user_setting_xiaobai = user_state.user_setting_xiaobai
        self.user_setting_dialect = user_state.user_setting_dialect
        self.Image_read = user_state.Image_read
        self.model_name = user_state.model_name
        print(f"{self.username}:self.model_name--{self.model_name}")
        
    
    def gen_calender(self):
        print(f"\n🎯 每日计划生成开始-------------")
        for day in range(len(self.calendar_module.calendar)):
            #print(f"\n📅 Day {day}: {self.calendar_module.calendar[day]['date']} {self.calendar_module.calendar[day]['weekday']} -------------------------------------------------")
            for Time_slot in ["morning", "afternoon", "evening"]:
                self.calendar_module.prepare_calendar(day,Time_slot)
            self.daily_update()
        
        # print(f"\n🎯 每日计划生成结束，Avatar开始生成执行细节------------")
        # self.reset_state() #重置虚拟人状态
        # self.external_event_manager.save_External_event_init() #重置外部事件库
        # for day in range(len(self.calendar_module.calendar)):
        #     #print(f"\n📅 Day {day}: {self.calendar_module.calendar[day]['date']} {self.calendar_module.calendar[day]['weekday']} -------------------------------------------------")
        #     for Time_slot in ["morning", "afternoon", "evening"]:
        #         self.calendar_module.play_calendar(day,Time_slot)
        #     self.daily_update()
        print(f"\n🎯 日历生成结束------------")

    def apply_behavior_feedback(self, behavior_name, success_value):
        behavior = self.cur_behavior_library[behavior_name] 

        # 获取行为权重匹配度
        bio_require = np.array(behavior["bio_require"])
        bio_cunsumption = np.array(behavior["bio_cunsumption"])
        bio_motivation = max(0.0, bio_cunsumption)

        psycho_cunsumption = np.array(behavior["psycho_cunsumption"])
        psycho_motivation = max(0.0, psycho_cunsumption)

        bio_weight = np.array(behavior["Weight"])[:3]
        psycho_social_weight = np.array(behavior["Weight"])[3:]
        norm_bio_weight = np.linalg.norm(bio_weight)
        norm_psycho_social_weight = np.linalg.norm(psycho_social_weight)

        personality1_bio_weight = self.personality[:3]
        personality1_psycho_social_weight = self.personality[3:]
        norm_personality_bio_weight = np.linalg.norm(personality1_bio_weight)
        norm_personality1_psycho_social_weight = np.linalg.norm(personality1_psycho_social_weight)

        state_bio_weight = self.bps_state_vector[:3]
        state_psycho_social_weight = self.bps_state_vector[3:]

        dot_bio_weight = np.dot(state_bio_weight, bio_weight) / (norm_personality_bio_weight * norm_bio_weight)
        dot_psycho_social_weight = np.dot(state_psycho_social_weight, psycho_social_weight) / (norm_personality1_psycho_social_weight * norm_psycho_social_weight)

        # 生理/心理反馈
        bio_cunsumption = np.array(behavior["bio_cunsumption"])
        psycho_cunsumption = np.array(behavior["psycho_cunsumption"])

        # 若成功：直接按比例加减
        # 若失败：放大负面反馈（消耗更大）
        success_value = np.clip(success_value,-1.0,1.0)

        if success_value > 0.0:
            if psycho_cunsumption > 0.0:
                psycho_cunsumption = abs(psycho_cunsumption) * abs(success_value)
            else:
                psycho_cunsumption = abs(psycho_cunsumption) * (1.0-abs(success_value)) # 成功降低了消耗感
        else:
            if psycho_cunsumption > 0.0:
                psycho_cunsumption = -abs(psycho_cunsumption)  * abs(success_value) # 失败带来了挫败感
            else:
                psycho_cunsumption = -abs(psycho_cunsumption) * abs(success_value)

        if bio_cunsumption > 0.0:
            self.bio_energy = np.clip(self.bio_energy + bio_cunsumption * dot_bio_weight * (success_value + 1.0) * 0.5, 0.0, 2.0)
        else:
            self.bio_energy = np.clip(self.bio_energy + bio_cunsumption * dot_bio_weight * (1.0 - success_value) * 0.5, 0.0, 2.0)

        # 倦怠调节（仅当行为执行了，无论成功与否）
        repeat_tolerance_score = self.bps_state_vector[5] * 0.4 + self.bps_state_vector[4] * 0.2 + self.bps_state_vector[10] * 0.2 + self.bps_state_vector[7] * 0.1 - self.bps_state_vector[3] * 0.1
        repeat_tolerance_score = np.clip(repeat_tolerance_score, 0.0, 1.0)
        repeat_tolerance_score *= dot_psycho_social_weight
        self.behavior_fatigue[behavior_name] = min(1.0, self.behavior_fatigue.get(behavior_name, 0) + 0.2 * (1.0 - repeat_tolerance_score))

        # 情绪反馈：调用情绪状态更新
        self.emotion_module.process_behavior(self.bio_energy, behavior, psycho_cunsumption * dot_psycho_social_weight, success_value)


    def daily_update(self):
        # 生理值/心理值/情绪 每天恢复
        self.bio_energy = np.clip(self.bio_energy * 0.8 + 0.2, 0.0, 2.0)
        self.emotion_module.valence = np.clip(self.emotion_module.valence * 0.2 + self.emotion_module.valence_baseline * 0.8, -1, 1.0)
        self.emotion_module.arousal = np.clip(self.emotion_module.arousal * 0.2 + 0.5 * 0.8, 0.0, 1.0)

        # 行动的倦怠值每日衰减
        for name in self.behavior_fatigue:
            self.behavior_fatigue[name] = max(0.0, self.behavior_fatigue[name] - 0.05)  

    def _softmax(self, x, temperature=1.0):
        x = np.array(x)
        x = x / temperature  # 控制选择的“激进程度”：越小越接近贪婪，越大越平均
        e_x = np.exp(x - np.max(x))  # 防止溢出
        return e_x / e_x.sum()
    
    def _split_keywords(self, keyword_str):
        if not '-' in keyword_str:
            parts = []
            parts.append(keyword_str)
            return parts
        parts = keyword_str.strip().split('-')
        return parts
    
    def _collect_values(self, data):
        values = []
        if isinstance(data, dict):
            for v in data.values():
                values.extend(self._collect_values(v))
        elif isinstance(data, list):
            values.extend(data)
        return values

    def _compute_average(self, data):
        all_values = self._collect_values(data)
        if not all_values:
            return 0
        return sum(all_values) / len(all_values)

    def _select_behavior(self, current_Time_slot="morning",life_style_weight = None,is_long_term_plan = False):
        scores = {}
        dynamic_choice_bias = 1.0
        self.emotion_module.decay()

        # 尝试混合外部库内容：
        # with open("./M_file/External_Event.json", "r", encoding="utf-8") as f:
        #     cur_External_behavior = json.load(f)

        # if not is_long_term_plan:
        #     if cur_External_behavior:
        #         #cur_behavior_library = self.behavior_library + cur_External_behavior
        #         self.cur_behavior_library = {**self.behavior_library, **cur_External_behavior}
        #         print("加入外部事件")
        #     else:
        #         self.cur_behavior_library = self.behavior_library
        # else:
        #     self.cur_behavior_library = cur_External_behavior

        self.cur_behavior_library = self.behavior_library

        for name, content in self.cur_behavior_library.items():   # 这里只从behavior_libarary中选择了内容，并未从外部事件库中选取啊
            if "Time" in content and current_Time_slot not in content["Time"]:
                continue

            bio_require = np.array(content["bio_require"])
            if bio_require > self.bio_energy:
                continue

            # if life_style_weight is not None:
            #     # ==== 动态 choice_bias，根据当天tag权重调节 ====
            #     tag = np.array(content.get("tag", [1,0,0,0,0]))  # 获取事件标签
            #     tag_weight_score = float(np.dot(tag, life_style_weight))  # 计算事件tag与当天活动权重的点积
            #     original_choice_bias = content.get("choice_bias", 1.0)
            #     dynamic_choice_bias = original_choice_bias * tag_weight_score


            # ==== 计算行动与人物BPS的匹配度 ====
            bio_cunsumption = np.array(content["bio_cunsumption"])
            bio_motivation = max(0.0, bio_cunsumption)

            psycho_cunsumption = np.array(content["psycho_cunsumption"])
            psycho_motivation = max(0.0, psycho_cunsumption)

            bio_weight = np.array(content["Weight"])[:3]
            psycho_social_weight = np.array(content["Weight"])[3:]
            norm_bio_weight = np.linalg.norm(bio_weight)
            norm_psycho_social_weight = np.linalg.norm(psycho_social_weight)

            personality1_bio_weight = self.personality[:3]
            personality1_psycho_social_weight = self.personality[3:]
            norm_personality_bio_weight = np.linalg.norm(personality1_bio_weight)
            norm_personality1_psycho_social_weight = np.linalg.norm(personality1_psycho_social_weight)

            state_bio_weight = self.bps_state_vector[:3]
            state_psycho_social_weight = self.bps_state_vector[3:]

            dot_bio_weight = np.dot(state_bio_weight, bio_weight) / (norm_personality_bio_weight * norm_bio_weight)
            dot_psycho_social_weight = np.dot(state_psycho_social_weight, psycho_social_weight) / (norm_personality1_psycho_social_weight * norm_psycho_social_weight)

            fatigue = self.behavior_fatigue.get(name, 0.0)
            fatigue_factor = pow(max(0.0, min(1.0, 1.0 - fatigue)), 0.25)

            # ==== 添加情绪影响 ====
            emotion_modifier = 1.0 + 0.25 * self.emotion_module.valence + 0.25 * (self.emotion_module.arousal - 0.5)
            emotion_modifier = np.clip(emotion_modifier, 0.75, 1.25)

            # ==== 抗拒因子（含情绪）====
            physical_resistance = pow(np.clip(self.bio_energy + bio_motivation * 0.5, 0.0, 1.0), 0.5) * emotion_modifier
            mental_resistance = pow(np.clip((self.emotion_module.valence*0.5+0.5) + psycho_motivation * 0.5, 0.0, 1.0), 0.5) * emotion_modifier

            # ==== 行为最终得分 ====
            if life_style_weight is not None:
                choice_bias = dynamic_choice_bias
            else:
                choice_bias = content.get("choice_bias", 1.0)
            bio_score = dot_bio_weight * choice_bias * fatigue_factor * physical_resistance
            psycho_social_score = dot_psycho_social_weight * choice_bias * fatigue_factor * mental_resistance

            score = (bio_score * (1.0 - self.bio_energy) + psycho_social_score * self.bio_energy) # 马斯洛 理论当生理能量不足时，更需要补充基本能量
            #score *= frustration_modifier  # 应用沮丧调节

            scores[name] = score

        return scores
    
    def _extract_all_strings(self, nested_data, prefix=""):
        """
        递归提取嵌套结构中所有的字符串，并带上键路径前缀（如 动画类-日漫动画-千与千寻）
        """
        results = []

        if isinstance(nested_data, str):
            results.append(f"{prefix}-{nested_data}" if prefix else nested_data)

        elif isinstance(nested_data, list):
            for item in nested_data:
                results.extend(self._extract_all_strings(item, prefix))

        elif isinstance(nested_data, dict):
            for key, value in nested_data.items():
                new_prefix = f"{prefix}-{key}" if prefix else key
                results.extend(self._extract_all_strings(value, new_prefix))

        return results

    def _apply_behavior(self, chosen_behavior, success_rate=0.5):

        if '情感-共情交流' in chosen_behavior:
            #与用户的共情交流成功率100%
            success_rate = 1.0

        match = re.search(r'【(.*?)】', chosen_behavior)
        if match:
            inner = match.group(1)
            outer = re.sub(r'【.*?】', '', chosen_behavior)
            chosen_behavior = outer.strip()
            selected_detail = inner.strip()
        else:
            chosen_behavior = chosen_behavior.strip()
            selected_detail = ''  # 没有括号内容时返回原始文本和空串
    
        # 随机生成行为成功与否（成功率可由匹配度决定，或者恒定90%）
        success = random.random() < success_rate
        if success:
            success = random.random() # 转为 0～1
        else:
            success = -random.random() #转为 -1～0

        # 执行行为反馈并更新情绪
        self.apply_behavior_feedback(chosen_behavior, success_value=success)
        self.print_state()

        favourite_value = -1.0

        if selected_detail == '':
            # 获取该行为的配置数据
            #behavior_data = self.behavior_library.get(chosen_behavior, {})  
            behavior_data = self.cur_behavior_library.get(chosen_behavior, {})
            if behavior_data == {}:
                # 出错了!
                print(f"apply_behavior:Error!{chosen_behavior} is not in behavior_library!")
                selected_detail = chosen_behavior
                pass
            else:
                path = "output/event_classification/sample_300_round3.json"
                data = {}
                with open(path,"r",encoding="utf-8") as f:
                    data = json.load(f)
                
                items = data.get(chosen_behavior,[]) 
                if items == []:
                    print(f"apply_behavior:Error!{chosen_behavior}-Detail is not exist!")
                    selected_detail = chosen_behavior
                else:
                    def parse_timestamp(ts):
                        if not ts:
                            return datetime.max

                        # 去掉时区部分，例如 +00:00
                        ts = ts.split("+")[0]

                        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")

                    current_dt = None if self.timestamp is None else parse_timestamp(self.timestamp)

                    valid_items = []

                    for item in items:
                        ts = item.get("timestamp")
                        if not ts:
                            continue
                        item_dt = parse_timestamp(ts)
                        if current_dt is None or item_dt > current_dt:
                            valid_items.append(item)

                    if valid_items:
                        choseitem = min(
                            valid_items,
                            key=lambda item: parse_timestamp(item.get("timestamp"))
                        )

                        selected_detail = choseitem.get("event_description")

                        self.timestamp = choseitem.get("timestamp")
                    else:
                        print(f"apply_behavior: Warning! no future event after {self.timestamp}")
                        selected_detail = chosen_behavior

                #details = behavior_data.get("Detail", [])
                #favourites = behavior_data.get("Favourite", [])

                # if details == []:
                #     # 出错了!
                #     print(f"apply_behavior:Error!{chosen_behavior}-Detail is not exist!")
                #     selected_detail = chosen_behavior
                favourites = []
                if favourites == []:
                    #新的数据库还未加入favorite选项,全部进行随机选择
                    # if isinstance(details,list):
                    #     selected_detail = random.choice(details)
                    # elif isinstance(details,dict):
                    #     items = []
                    #     for item, content in details:
                    #         items.append(item)
                    #     selected_detail = random.choice(items)

                    #     if isinstance(details[selected_detail],list):
                    #         selected_detail = selected_detail+"-"+ random.choice(details[selected_detail])
                    #     elif isinstance(details[selected_detail],dict):
                    #         L_items = []
                    #         for l_item,content in details[selected_detail]:
                    #             L_items.append(l_item)
                    #         l_selectd = random.choice(L_items)
                    #         selected_detail = selected_detail+"-"+ l_selectd + "-" + random.choice(details[selected_detail][l_selectd])
                    
                    #print(selected_detail)
                    pass
                        
                else: 
                    # 递归提取所有可选字符串项
                    # 第一级
                    all_items = self._extract_all_strings(details)
                    if len(all_items)==0:
                        # 出错了!
                        selected_detail = chosen_behavior
                    else:
                        L1_key_list = []
                        for item in all_items:
                            keys = self._split_keywords(item)
                            L1_key_list.append(keys[0])
                        # 获得唯一的L1_Key的list
                        L1_unique_key_list = list(set(L1_key_list))
                        L1_unique_key_value = []
                        if isinstance(favourites, list):#喜好评分列表分为2种，1、全体一个分。2、分项给分
                            if len(favourites) == len(L1_unique_key_list):
                                # 各自赋值
                                L1_unique_key_value = favourites
                            else:
                                if len(favourites)==1:
                                    # 长度为1,所有key都用同一个值
                                    for l1 in L1_unique_key_list:
                                        L1_unique_key_value.append(favourites[0])
                                else:
                                    # 出错了,用1.0数值来填充
                                    for l1 in L1_unique_key_list:
                                        L1_unique_key_value.append(1.0)
                        elif isinstance(favourites, dict):#说明还有更细分的得分，因此计算一下
                            for item in L1_unique_key_list:
                                if item in favourites:
                                    key_value = self._compute_average(favourites[item])
                                    L1_unique_key_value.append(key_value)
                                else:
                                    # 出错了,用0.5数值来填充
                                    L1_unique_key_value.append(0.5)
                        else:
                            print(f"apply_behavior:Error!{chosen_behavior}-Favourites is not dict or list")
                            pass

                        #通过喜爱值来影响概率.获得第一个合理的选项
                        if sum(L1_unique_key_value) >0:
                            L1_key_select = random.choices(L1_unique_key_list,weights=L1_unique_key_value,k=1)[0]
                        else:
                            L1_key_select = random.choice(L1_unique_key_list)

                        selected_detail = L1_key_select
                        #获得对应的喜爱值
                        for index in range(0,len(L1_unique_key_list)):
                            if L1_key_select == L1_unique_key_list[index]:
                                favourite_value = L1_unique_key_value[index]
                                break
                        
                        # 第二级
                        L2_key_list = []
                        for item in all_items:
                            keys = self._split_keywords(item)
                            if L1_key_select in keys[0]:
                                if len(keys)>=2:
                                    L2_key_list.append(keys[1])
                        if len(L2_key_list)>0:
                            L2_unique_key_list = list(set(L2_key_list))
                            L2_unique_key_value = []
                            if isinstance(favourites, dict):#只有上一级为dict，才会有下一级的处理
                                if L1_key_select in favourites:
                                    if isinstance(favourites[L1_key_select], list):#喜好评分列表分为2种，1、全体一个分。2、分项给分
                                        if len(favourites) == len(L2_unique_key_list):
                                            # 各自赋值
                                            L2_unique_key_value = favourites[L1_key_select]
                                        else:
                                            if len(favourites[L1_key_select])==1:
                                                # 长度为1,所有key都用同一个值
                                                for l2 in L2_unique_key_list:
                                                    L2_unique_key_value.append(favourites[L1_key_select][0])
                                            else:
                                                # 出错了,用1.0数值来填充
                                                for l2 in L2_unique_key_list:
                                                    L2_unique_key_value.append(1.0)
                                    elif isinstance(favourites[L1_key_select], dict):#说明还有更细分的得分，因此计算一下
                                        for item in L2_unique_key_list:
                                            key_value = self._compute_average(favourites[L1_key_select])
                                            L2_unique_key_value.append(key_value)
                                    else:
                                        for l2 in L2_unique_key_list:
                                            L2_unique_key_value.append(1.0)
                                    if sum(L2_unique_key_value)>0:
                                        L2_key_select = random.choices(L2_unique_key_list,weights=L2_unique_key_value,k=1)[0]
                                    else:
                                        L2_key_select = random.choice(L2_unique_key_list)
                                    for index in range(0,len(L2_unique_key_list)):
                                        if L2_key_select == L2_unique_key_list[index]:
                                            favourite_value = L2_unique_key_value[index]
                                            break
                                else:
                                    # 出错了,随机选一个
                                    print(f"apply_behavior:Error!{chosen_behavior}-{L1_key_select} not in Favourites")
                                    L2_key_select = random.choice(L2_unique_key_list)
                            else:
                                # 出错了,随机选一个
                                print(f"apply_behavior:Error!{chosen_behavior}-Favourites is not dict")
                                L2_key_select = random.choice(L2_unique_key_list)
                            selected_detail = selected_detail + "-" + L2_key_select

                            # 第三级
                            L3_key_list = []
                            for item in all_items:
                                keys = self._split_keywords(item)
                                if L1_key_select in keys[0]:
                                    if len(keys)>=2 and L2_key_select in keys[1]:
                                        if len(keys)>=3:
                                            L3_key_list.append(keys[2])
                            if len(L3_key_list)>0:
                                L3_unique_key_list = list(set(L3_key_list))
                                L3_unique_key_value = []
                                if isinstance(favourites, dict):#只有上一级为dict，才会有下一级的处理
                                    if L1_key_select in favourites:
                                        if isinstance(favourites[L1_key_select], dict):#只有上一级为dict，才会有下一级的处理
                                            if L2_key_select in favourites[L1_key_select]:
                                                if isinstance(favourites[L1_key_select][L2_key_select], list):#喜好评分列表分为2种，1、全体一个分。2、分项给分
                                                    if len(favourites[L1_key_select][L2_key_select]) == len(L3_unique_key_list):
                                                        L3_unique_key_value = favourites[L1_key_select][L2_key_select]
                                                    else:
                                                        if len(favourites[L1_key_select][L2_key_select])==1:
                                                            for l3 in L3_unique_key_list:
                                                                L3_unique_key_value.append(favourites[L1_key_select][L2_key_select][0])
                                                        else:
                                                            for l3 in L3_unique_key_list:
                                                                L3_unique_key_value.append(1.0)
                                                elif isinstance(favourites[L1_key_select][L2_key_select], dict):#说明还有更细分的得分，因此计算一下
                                                    for item in L3_unique_key_list:
                                                        key_value = self._compute_average(favourites[L1_key_select][L2_key_select])
                                                        L3_unique_key_value.append(key_value)
                                                else:
                                                    for l3 in L3_unique_key_list:
                                                        L3_unique_key_value.append(1.0)
                                                print(f"L3_unique_key_value:{L3_unique_key_value}")
                                                if sum(L3_unique_key_value)>0:
                                                    L3_key_select = random.choices(L3_unique_key_list,L3_unique_key_value,k=1)[0]
                                                else:
                                                    L3_key_select = random.choice(L3_unique_key_list)

                                                for index in range(0,len(L3_unique_key_list)):
                                                    if L3_key_select == L3_unique_key_list[index]:
                                                        favourite_value = L3_unique_key_value[index]
                                                        break
                                            else:
                                                # 出错了,随机选一个
                                                print(f"apply_behavior:Error!{chosen_behavior}-{L1_key_select}-{L2_key_select} not in Favourites")
                                                L3_key_select = random.choice(L3_unique_key_list)
                                        else:
                                            # 出错了,随机选一个
                                            print(f"apply_behavior:Error!{chosen_behavior}-{L1_key_select}-Favourites is not dict")
                                            L3_key_select = random.choice(L3_unique_key_list)
                                    else:
                                        # 出错了,随机选一个
                                        print(f"apply_behavior:Error!{chosen_behavior}-{L1_key_select} not in Favourites")
                                        L3_key_select = random.choice(L3_unique_key_list)
                                else:
                                    # 出错了,随机选一个
                                    print(f"apply_behavior:Error!{chosen_behavior}-Favourites is not dict")
                                    L3_key_select = random.choice(L3_unique_key_list)
                                selected_detail = selected_detail + "-" + L3_key_select
                        
        if favourite_value > 0.8:
            favourite_value = "(非常喜欢做)"
        elif favourite_value > 0.6:
            favourite_value = "(很喜欢做)"
        elif favourite_value > 0.4:
            favourite_value = "(喜欢做)"
        elif favourite_value > 0.2:
            favourite_value = "(不喜欢做)"
        elif favourite_value >= 0.0:
            favourite_value = "(讨厌做)"
        else:
            favourite_value = "" # favourite_value = -1.0
        # else:
        #     favourite_value = ""

        if success > 0.5:
            success = "实现目标"
        elif success > 0.25:
            success = "进展顺利"
        elif success > 0.0:
            success = "小有收获"
        elif success > -0.25:
            success = "情况不妙"
        elif success > -0.5:
            success = "状况堪忧"
        else:
            success = "惨遭失败"

        return chosen_behavior + "【" + selected_detail + favourite_value + "】", success

    def select_best_behavior(self, top_k=3, current_Time_slot="morning",life_style_weight=None, Softmax=True, temperature=1.0,is_long_term_plan = False):
        scores = self._select_behavior(current_Time_slot,life_style_weight,is_long_term_plan = is_long_term_plan)

        # 选择 Top-K
        if not scores:
            return None, {}
        top_behaviors = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        names, raw_scores = zip(*top_behaviors)

        if Softmax:
            # 计算 Softmax 概率
            probabilities = self._softmax(raw_scores, temperature=temperature)
            chosen_behavior = random.choices(names, weights=probabilities, k=1)[0]
        else:
            # 计算 平均 概率
            total_score = sum(raw_scores)
            probabilities = [v / total_score for v in raw_scores] if total_score > 0 else [1 / len(raw_scores)] * len(raw_scores)
            chosen_behavior = random.choices(names, weights=probabilities, k=1)[0]
        
        behavior_apply_detail, result = self._apply_behavior(chosen_behavior, self.luck) # 这里成功率先设定为0.5--->改动为0.6
        item = {
            "🔋 体力值: " :self.bio_energy,
            "🔋 情绪效价: " :self.emotion_module.current_mood_valence(),
            "🔋 情绪唤醒:" :self.emotion_module.current_mood_arousal(),
            "behavior_name":chosen_behavior,
            "behavior_apply_detail":behavior_apply_detail,
            "behavior_result":result,
            "score":scores[chosen_behavior]
        }

        self.atm_action_list.append(item)
        print(f"behavior_name: {chosen_behavior},\nbehavior_apply_detail:{behavior_apply_detail}\nbehavior_result:{result}\n score:{scores[chosen_behavior]}\n")
        
        return ({
                    "behavior_name": chosen_behavior,          # 行为名，比如 "社交-朋友聚会"
                    "behavior_detail": behavior_apply_detail,  # 原始的最终文本，比如 "社交-朋友聚会【唱K】"
                    "behavior_result": result,                 # 进展顺利
                    "score": scores[chosen_behavior]           # 分数
                }, scores)
        
    def get_adjusted_state(self):
        return self.bps_state_vector

    def print_state(self):
        print("🔋 体力值: " + str(self.bio_energy))
        print("🔋 情绪效价:" + self.emotion_module.current_mood_valence())
        print("🔋 情绪唤醒:" + self.emotion_module.current_mood_arousal())
        dim_names = [
            "生理健康需求", "疼痛规避需求", "健康保护需求", "情绪反应需求",
            "风险规避需求", "目标坚持需求", "好奇探索需求", "规范遵循需求",
            "亲社会性需求", "社会形象需求", "角色责任需求", "群体归属需求"
        ]
        
        if len(self.bps_state_vector) != len(dim_names):
            print(f"⚠️ 状态向量维度数（{len(self.bps_state_vector)}）与名称数量不匹配（{len(dim_names)}）")
            return
        #print("\n".join(f"{name}: {round(val, 3)}" for name, val in zip(dim_names, self.bps_state_vector)))

    def get_state_str(self):
        hour = datetime.now().hour
        if 5 < hour < 12:
            period = 'morning'
        elif 12 <= hour < 18:
            period = 'afternoon'
        elif 18 <= hour < 24:
            period = 'evening'
        else:
            period = 'evening'

        today = datetime.today()
        for iter in range(0,len(self.calendar_module.calendar)):
            if today.strftime('%Y-%m-%d') == self.calendar_module.calendar[iter]["date"]:
            
                self.bio_energy = self.calendar_module.calendar[iter][period]["avatar_bio_energy_play"]
                self.emotion_module.arousal = self.calendar_module.calendar[iter][period]["avatar_mood_arousal_play"]

                bio_energy_raw = self.bio_energy
                mood_arousal_raw = self.emotion_module.arousal 
                
                if self.calendar_module.calendar[iter][period]["avatar_mood_valence_play"]<-1:
                    self.emotion_module.valence = self.emotion_module.valence_baseline
                else:
                    self.emotion_module.valence = self.calendar_module.calendar[iter][period]["avatar_mood_valence_play"]
                print("小白情绪、状态已读取") 
                mood_valence_raw = self.emotion_module.valence
                break
        
        bio_energy_str = ""
        if self.bio_energy > 0.5:
            bio_energy_str = "体力充沛"
        elif self.bio_energy > 0.2:
            bio_energy_str = "体力正常"
        elif self.bio_energy > 0.1:
            bio_energy_str = "体力虚弱" 
        else:
            bio_energy_str = "体力疲惫" 

        mood_valence_str = self.emotion_module.current_mood_valence()
        mood_arousal_str = self.emotion_module.current_mood_arousal()

        return bio_energy_str,mood_valence_str,mood_arousal_str,bio_energy_raw,mood_valence_raw,mood_arousal_raw

# 每个行为的定义格式：基于Biopsychosocial的需求描述
#   "行为类型": {
#       "tag": string → 行为的类别 
#       "choice_bias": float → 行为被选中的倾向值（>1 更容易被选中，<1 更难被选中）
#       "bio_require": float → 行为要求的基本体力值（范围0~1:0代表没有基本体力要求，1代表要求体力充沛）
#       "bio_cunsumption": float → 行为执行后带来的体力值消耗（范围-1～1:-1代表对体力值减少，0代表对体力值无增无减，1代表体力值被恢复）
#       "psycho_cunsumption": float → 行为执行后带来的心理值消耗（范围-1～1:-1代表对心理值减少，0代表对心理值无增无减，1代表心理值被恢复）
#       "Weight": List[float] → 虚拟人的需求匹配，用于与虚拟人的12维状态进行点乘计算（下列为12维状态中每个参数的解释）
            #"biological_physiological_drive"      // 生理-本能需求：身体本能
            #"biological_pain_avoidance"           // 生理-伤害规避：规避风险、规避伤害
            #"biological_health_preservation"      // 生理-健康保护：保全身体、避免消耗
            #"psychological_emotional_reactivity"  // 心理-情绪激发：外部事件引发高情绪波动
            #"psychological_risk_aversion"         // 心理-风险规避：避免冲突、不确定或危险情境
            #"psychological_goal_persistence"      // 心理-目标坚持：坚持长远目标、抵抗诱惑
            #"psychological_curiosity_drive"       // 心理-探索好奇：新事物与未知经验的倾向
            #"social_norm_adherence"               // 社会-规范遵循：守规矩、按制度行事的程度
            #"social_prosocial_motivation"         // 社会-利他倾向：利他主义、帮助他人的倾向
            #"social_self_presentation"            // 社会-面子维护：在他人面前关注个体形象与体面
            #"social_role_duty_sense"              // 社会-角色责任：根据角色身份（如老师、父母）做出义务行为
            #"social_group_affiliation"            // 社会-群体归属：对团体的忠诚、集体目标的优先级
#       "Time": List[string] → "morning", "afternoon", "evening"
#       "Detail": List[string]
#   }

#基于Biopsychosocial的需求
#一个爱学习，低社交需求的人
personality1 = np.array([
    0.5,  # biological_physiological_drive     生理能量中等
    0.4,  # biological_pain_avoidance          伤害规避偏低
    0.6,  # biological_health_preservation     健康保护中等偏高
    0.5,  # psychological_emotional_reactivity 情绪激发性中等
    0.4,  # psychological_risk_aversion        风险规避偏低
    1.5,  # psychological_goal_persistence     目标坚持度高
    1.1,  # psychological_curiosity_drive      探索动机中等偏高
    0.2,  # social_norm_adherence              社会规范遵循低
    0.1,  # social_prosocial_motivation        亲社会动机低
    0.1,  # social_self_presentation           自我呈现/面子需求很低
    0.1,  # social_role_duty_sense             社会角色责任感低
    0.1   # social_group_affiliation           群体归属感低
])

#基于Biopsychosocial的需求
#一个高社交需求、善解人意的人
personality2 = np.array([
    0.6,  # biological_physiological_drive     生理能量中等偏高
    0.5,  # biological_pain_avoidance          伤害规避中等
    0.6,  # biological_health_preservation     健康保护中等
    0.7,  # psychological_emotional_reactivity 情绪激发性较高
    0.6,  # psychological_risk_aversion        风险规避中等偏高
    0.7,  # psychological_goal_persistence     目标坚持度较高
    0.5,  # psychological_curiosity_drive      探索动机中等
    0.7,  # social_norm_adherence              社会规范遵循高
    1.5,  # social_prosocial_motivation        亲社会动机非常高 ← 善解人意关键
    1.4,  # social_self_presentation           社会面子需求高（愿意被认同）
    1.5,  # social_role_duty_sense             社会责任感非常高 ← 善解人意关键
    1.4   # social_group_affiliation           群体归属感高 ← 高社交需求关键
])

#基于Biopsychosocial的驱动
#一个爱学习的人，性格开朗，爱运动的人
personality3 = np.array([
    0.9,  # biological_physiological_drive     生理能量高 ← 爱运动
    0.3,  # biological_pain_avoidance          疼痛规避低 ← 运动接受度高
    0.6,  # biological_health_preservation     健康保护中等
    0.8,  # psychological_emotional_reactivity 情绪激发性高 ← 性格开朗
    0.3,  # psychological_risk_aversion        风险规避低 ← 运动型探索型
    1.2,  # psychological_goal_persistence     目标坚持度高 ← 爱学习
    1.2,  # psychological_curiosity_drive      探索动机高 ← 爱学习
    0.7,  # social_norm_adherence              社会规范遵循中等偏高 ← 学习型
    0.9,  # social_prosocial_motivation        亲社会动机高 ← 性格外向
    0.9,  # social_self_presentation           面子需求高 ← 活跃外向
    0.7,  # social_role_duty_sense             社会责任感中等偏高
    0.9   # social_group_affiliation           群体归属感高 ← 喜社交运动
])

#基于Biopsychosocial的驱动
#一个热爱冒险，不怕风险，且喜欢独行的人
personality4 = np.array([
    1.5,  # biological_physiological_drive     生理能量高 ← 喜欢高体能挑战
    0.2,  # biological_pain_avoidance          疼痛规避很低 ← 敢冒险
    0.4,  # biological_health_preservation     健康保护偏低 ← 接受身体消耗
    1.4,  # psychological_emotional_reactivity 情绪激发性较高 ← 对冒险有兴奋感
    0.1,  # psychological_risk_aversion        风险规避极低 ← 不怕危险
    0.6,  # psychological_goal_persistence     目标坚持中等偏高 ← 能完成挑战
    1.5,  # psychological_curiosity_drive      探索动机极高 ← 热爱未知
    0.3,  # social_norm_adherence              社会规范遵循偏低 ← 较叛逆
    0.1,  # social_prosocial_motivation        亲社会动机低 ← 喜欢独行
    0.2,  # social_self_presentation           面子需求中等 ← 不太在意他人看法
    0.1,  # social_role_duty_sense             社会责任感低 ← 不受角色束缚
    0.1   # social_group_affiliation           群体归属感极低 ← 独行者
])

#基于Biopsychosocial的驱动
#一个爱玩不爱学习的人
personality5 = np.array([
    1.0,  # biological_physiological_drive     → 很爱动，偏好体感与刺激
    0.4,  # biological_pain_avoidance          → 不太怕辛苦，但不做痛苦事
    0.3,  # biological_health_preservation     → 健康意识低，易沉迷玩乐
    0.9,  # psychological_emotional_reactivity → 玩乐情绪反应强烈
    0.2,  # psychological_risk_aversion        → 风险意识很低，容易做冲动决策
    0.1,  # psychological_goal_persistence     → 极低的目标坚持度，无法坚持学习任务
    0.9,  # psychological_curiosity_drive      → 好奇心高但不深入（偏向浅层体验）
    0.3,  # social_norm_adherence              → 抗拒规矩、不守课堂纪律
    0.2,  # social_prosocial_motivation        → 不愿配合学习活动或集体目标
    0.6,  # social_self_presentation           → 在乎别人怎么看自己“酷不酷”
    0.2,  # social_role_duty_sense             → 学生角色责任感低
    0.4   # social_group_affiliation           → 不强烈归属感，可能逃避集体学习情境
])

# 工作狂（Goal-driven Workaholic）
personality_workaholic = np.array([
    0.5,  # biological_physiological_drive      生理精力中等
    0.7,  # biological_pain_avoidance           能忍耐疲劳，但仍注意身体
    0.8,  # biological_health_preservation      重视健康（为了持续工作）

    0.4,  # psychological_emotional_reactivity  情绪稳定，不容易受外界影响
    0.8,  # psychological_risk_aversion         做事谨慎
    1.5,  # psychological_goal_persistence      ★极强目标坚持
    1.0,  # psychological_curiosity_drive       有学习欲望，但主要服务于工作

    1.2,  # social_norm_adherence               ★遵守制度、守时守规
    0.5,  # social_prosocial_motivation         社交一般，不主动闲聊
    0.8,  # social_self_presentation            希望表现专业可靠
    1.4,  # social_role_duty_sense              ★责任感极高
    0.5   # social_group_affiliation            群体归属一般，更重视任务
])

#乐观派
emotional1 = np.array([
    0.0, # 当前的情绪效价（范围 -1.0 ~ 1.0），
    0.1, # 情绪效价的个体基准线（个性倾向），可用于表示一个人天生偏悲观或乐观（例如 -0.2 表示略偏负面）（范围 -1.0 ~ 1.0），
    0.5, # 情绪恢复速度（范围 0.0 ~ 1.0），
    0.5 # 个体对事件刺激的情绪反应强度（放大倍数），值越大 → 对行为结果更敏感，情绪波动更剧烈（范围 0.0 ~ 1.0），
])

#悲观派
emotional2 = np.array([
    0.0, # 当前的情绪效价（范围 -1.0 ~ 1.0），
    -0.2, # 情绪效价的个体基准线（个性倾向），可用于表示一个人天生偏悲观或乐观（例如 -0.2 表示略偏负面）（范围 -1.0 ~ 1.0），
    0.5, # 情绪恢复速度（范围 0.0 ~ 1.0），
    0.5 # 个体对事件刺激的情绪反应强度（放大倍数），值越大 → 对行为结果更敏感，情绪波动更剧烈（范围 0.0 ~ 1.0），
])
from pathlib import Path


def save(data,path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path):
    with open(path,"r",encoding = "utf-8") as f:
        data = json.load(f)

    return data

import os
if __name__ == "__main__":
    event_out_path = f"output/event_classification/Event_pool.json"
    data = load_json(event_out_path)

    agent = VirtualAgent(personality_workaholic,emotional1,behavior_library = data)

    agent.gen_calender()

    path = "output/atm_action/ActionList2.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path,"w",encoding="utf-8") as f:
        json.dump(agent.atm_action_list,f,ensure_ascii=False,indent=2)
