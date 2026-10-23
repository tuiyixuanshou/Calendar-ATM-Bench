import json
import os
import re
import time as time_module
import requests
import random
import threading
import statistics
import LLM_interface
import chinese_calendar as chinese_calendar
from lunarcalendar import Converter, Solar, Lunar
from datetime import datetime, timedelta, time
from openai import OpenAI
#from Calendar_autoUpdate import git_pull
#from tool import ensure_temp_dir

def ensure_temp_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

class Calendar:
    def __init__(self, agent, days=3, path="AvatarCalendar.json",username = None,agent_name = None, is_main_server = False):
        self.agent = agent
        if agent_name != None:
            self.default_agent_name = agent_name
        else:
            self.default_agent_name = "小白"

        self.days = days
        self.path = path
        #self.CalendarList = "./Calendar_List"
        self.AgentCalendarList = "./agent_Calendar_List"
        #ensure_temp_dir(self.CalendarList)
        ensure_temp_dir(self.AgentCalendarList)
        self.weekday_map = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        self.username = username
        self.world_plan = self._load_world_plan()

        self.is_main_server = is_main_server
        self.calendar = []
        self._init_calendar()

        self.is_follow_git = True # 为True的就是直接覆盖git，为False的就是自动生成的。

    def _load_world_plan(self):
        ensure_temp_dir('./config')
        data = {}
        try:
            with open("./config/world_plan_record.json",'r',encoding='utf-8') as f:
                data = json.load(f)
            return data
        # except: 
        #     print('没有找到./config/world_plan_record.json配置文件，data为空')
        #     return data
        except FileNotFoundError:
            #raise FileNotFoundError(f"配置文件 {path} 未找到")
            print('没有找到./config/world_plan_record.json配置文件，data为空')
            return data
        except json.JSONDecodeError as e:
            #raise ValueError(f"配置文件格式错误: {e}")
            print(f'./config/world_plan_record.json配置文件格式错误:{e}')
            return data
        except Exception as e:
            print(f"读取配置文件config/world_plan_record.json失败: {e}")
            return data
    
    def _fill_period(self, date, period: str):
        #日历数据结构
        #weather = self._get_weather_by_period(city, date, period)
        #holiday = self._get_holiday(date)  # 好像使用的文件包还没有更新2026年的日历。

        return {
            #"state_vector": [], #avatar读取当前状态
            "status": "", # 不确定 random_plan,world_plan,user_plan,role_play  world_plan给出权重，world_plan映射到state vector上
            "world_plan":"", # 公共
            "weather":"",    # 公共
            #"holiday": holiday, # 公共
            "holiday": "无", # 公共
            "life_style_weight":[1.0,1.0,1.0,1.0,1.0],# 公共第一个：生理性 第二个：工作性质 第三个：休闲性质 第四个：社交性质 第五个：情感性质
            "task_planning":"",         # 公共 当前计划做的事件
            "task_result":"",          
            "task_planning_score":0.5,  # 公共 当前计划做的事件的权重
            "task_details": "",         # 公共 当前实际执行的事件的具体行动描述
            "task_prompt":"",           # 公共 文生图的Prompt
            "task_reminder":"",         # 私人 当天需要提醒的重要信息
            "avatar_bio_energy":-1.0,   # 公共 avatar的体力
            "avatar_mood_valence":-1.0, # 公共 avatar的情绪效价
            "avatar_mood_arousal":-1.0, # 公共 avatar的情绪唤醒
            "avatar_behavior_fatigue":{}, # 公共 对每件事的倦怠程度
            "avatar_luck":-1.0,         # 公共 avatar执行的成功率
            "avatar_bio_energy_play":-1.0,   # 公共 avatar play_calendar中的体力
            "avatar_mood_valence_play":-1.0, # 公共 avatar play_calendar中的情绪效价
            "avatar_mood_arousal_play":-1.0, # 公共 avatar play_calendar中的情绪唤醒
            "avatar_behavior_fatigue_play":{}, # 公共 对每件事的倦怠程度
            "avatar_location":"北京",   # 公共 avatar所处的城市
            "user_task": "",            # 私人
            "is_Pre":False,             # 公共，且用于判断 是否进行过prepare_calendar
            "is_Play":False            # 公共，且用于判断 是否进行过play_calendar
        }
    
    # def has_user_task(calendar, _day_index, _time_slot):
    #     return 'user_task' in calendar.get(_day_index, {}).get(reverse_time_slot.get(_time_slot, ''), {})

    def _solar_to_lunar(self, date: datetime.date) -> str:
        """
        将 datetime.date 类型的公历日期转换为农历字符串。
        """
        solar = Solar(year=date.year, month=date.month, day=date.day)
        lunar = Converter.Solar2Lunar(solar)

        # 输出格式示例：农历 2025年四月三十
        day_name = str(lunar.day)+"号"
        month_name = str(lunar.month)
        if lunar.day == 1:
            day_name = "初一"
        if lunar.day == 2:
            day_name = "初二"
        if lunar.day == 3:
            day_name = "初三"
        if lunar.day == 4:
            day_name = "初四" 
        if lunar.day == 5:
            day_name = "初五" 
        if lunar.day == 15:
            day_name = "十五" 
        if lunar.month == 1:
            month_name = "正"
        if lunar.month == 12:
            month_name = "腊"
        return f"农历{month_name}月{day_name}"

    def _get_holiday(self, date):
        # 判断是否为节假日
        is_holiday = chinese_calendar.is_holiday(date)

        # 获取节日详情
        on_holiday, holiday_name = chinese_calendar.get_holiday_detail(date)

        on_workday = chinese_calendar.is_workday(date)	# 是否为工作日（含补班日）
        in_lieu = chinese_calendar.is_in_lieu(date)	# 是否为调休日（周末但补班）
        lunar = self._solar_to_lunar(date)

        if in_lieu:
            return "调休,周末但补班"
        if on_holiday:
            if not holiday_name :
                holiday_name = "暂无"
            return holiday_name + "(" + lunar + ")"
        if not on_workday:
            return "周末"
        return "无"

    def _get_weather_by_period(self, city: str, date, period: str):
        date = date.strftime('%Y-%m-%d')
        city_coords = {
            "北京": (39.9042, 116.4074),
            "上海": (31.2304, 121.4737),
            "杭州": (30.2741, 120.1551),
            "成都": (30.5728, 104.0668),
            "南京": (32.0603, 118.7969),
            "深圳": (22.5431, 114.0579),
            "洛杉矶": (34.0522, -118.2437)
        }

        if city not in city_coords:
            return "城市暂不支持"

        def determine_time_range(period: str):
            """根据时段名称返回小时范围"""
            if period == "morning":
                return range(6, 12)
            elif period == "afternoon":
                return range(12, 18)
            elif period == "evening":
                return range(18, 24)
            else:
                return None  # 支持未来扩展更多时段名
    
        hours = determine_time_range(period)
        if not hours:
            return "不支持的时段名，请使用 '上午'、'下午' 或 '晚上'"

        lat, lon = city_coords[city]

        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&hourly=temperature_2m,weathercode,precipitation_probability,"
            f"relative_humidity_2m,windspeed_10m"
            f"&timezone=auto&start_date={date}&end_date={date}"
        )

        response = requests.get(url)
        if response.status_code != 200:
            return "天气数据获取失败"

        data = response.json()
        hourly = data["hourly"]
        times = hourly["time"]

        temps, winds, humidities, rain_probs, codes = [], [], [], [], []

        for i, t in enumerate(times):
            hour = int(t[-5:-3])
            if hour in hours:
                temps.append(hourly["temperature_2m"][i])
                winds.append(hourly["windspeed_10m"][i])
                humidities.append(hourly["relative_humidity_2m"][i])
                rain_probs.append(hourly["precipitation_probability"][i])
                codes.append(hourly["weathercode"][i])

        if not temps:
            return f"{date} {period} 时段无天气数据"

        median_wind = round(statistics.median(winds), 1)
        def wind_feel(h):
            if h <= 6:
                return "无风"
            elif h < 20:
                return "微风"
            elif h <= 28:
                return "和风"
            elif h <= 49:
                return "强风"
            else:
                return "狂风"
        median_wind = wind_feel(median_wind)
        
        median_humidity = round(statistics.median(humidities), 1)
        median_rain_prob = round(statistics.median(rain_probs), 1)
        code = max(set(codes), key=codes.count)

        weather_map = {
            0: "晴", 1: "晴", 2: "多云", 3: "阴天", 45: "薄雾", 48: "霜雾",
            51: "轻微毛毛雨", 53: "中等毛毛雨", 55: "密集毛毛雨",
            61: "小雨", 63: "中雨", 65: "大雨", 66: "轻微冻雨", 67: "强冻雨",
            71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
            80: "局部小阵雨", 81: "中等阵雨", 82: "强阵雨",
            85: "局部小阵雪", 86: "局部大阵雪",
            95: "雷暴", 96: "雷暴夹冰雹", 99: "强雷暴夹冰雹"
        }

        median_temp = round(statistics.median(temps), 1)
        def tempture_feel(h):
            if h <= 5:
                return "寒冷"
            elif h <= 20:
                return "舒适"
            else:
                return "炎热"
        median_temp = tempture_feel(median_temp)

        def humidity_feel(h):
            if median_temp == "寒冷":
                if h <= 50:
                    return "寒冷干燥"
                elif h <= 70:
                    return "寒冷"
                else:
                    return "寒冷湿冷"
            elif median_temp == "舒适":
                if h <= 50:
                    return "干爽"
                elif h <= 70:
                    return "舒适"
                else:
                    return "潮湿"
            else:
                if h <= 60:
                    return "炎热干燥"
                elif h <= 70:
                    return "炎热"
                else:
                    return "闷热潮湿"
        median_humidity = humidity_feel(median_humidity)

        precip_prob = pow(median_rain_prob / 100.0, 0.5)
        r = random.random()

        if r < precip_prob:
            # 下雨了
            weather = weather_map.get(max(51,code), "晴天") 
            return (f"天气:{weather},{median_humidity},{median_wind}")
        else:
            # 没下雨
            weather = weather_map.get(min(3,code), "晴天") 
            return (f"天气:{weather},{median_humidity},{median_wind}")
    
    def Update_Weather(self,isCurrent = True):
        if isCurrent: #更新现在的天气状况
            hour = datetime.now().hour
            hour = datetime.now().hour
            if 5 < hour < 12:
                period = 'morning'
            elif 12 <= hour < 18:
                period = 'afternoon'
            elif 18 <= hour < 24:
                period = 'evening'
            else:
                period = 'evening'
            weather = self._get_weather_by_period(self.agent.location, datetime.today(), period)
            today = datetime.today()
            for iter in range(0,len(self.calendar)):
                if today.strftime('%Y-%m-%d') == self.calendar[iter]["date"]:
                    self.calendar[iter][period]["weather"] = weather
                    self.save_calendar()
                    return
            print("更新天气失败")
        
        else: #更新当天的天气状态
            periods = ["morning", "afternoon", "evening"]
            today = datetime.today()
            for iter in range(0,len(self.calendar)):
                if today.strftime('%Y-%m-%d') == self.calendar[iter]["date"]:
                    for period in periods:
                        weather = self._get_weather_by_period(self.agent.location, datetime.today(), period)
                        self.calendar[iter][period]["weather"] = weather
                    self.save_calendar()
                    return
            print("更新天气失败")
    
    def Get_Weather(self):
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
        for iter in range(0,len(self.calendar)):
            if today.strftime('%Y-%m-%d') == self.calendar[iter]["date"]:
                weather = self.calendar[iter][period]["weather"]
                return weather
        
        return None

    def _init_calendar(self):
        """生成基础日历结构,公共日历/私人日历"""
        # === 1. 确定读取路径 & 加载旧日历（如果存在） === #
        if self.username == None or self.agent.agent_name != None:  # 公共日历生成维护  或者生成单独的agent日历  面向用户的agent不用提供名字。但是agent相互对话的agent需要名字
            if self.is_main_server:  # 只有主服务器才配更新
                old_calendar = []

                if self.agent.agent_name != None:
                    print("合并日历路径")
                    self.path = os.path.join(self.AgentCalendarList,self.path)
                    print(self.path)
            
                if os.path.exists(self.path):
                    try:
                        with open(self.path, "r", encoding="utf-8") as f:
                            old_calendar = json.load(f)
                    except Exception as e:
                        print(f"⚠️ 日历读取失败：{self.path}, 错误: {e}")
                        old_calendar = []

                today = datetime.today()
                self.calendar = []
                #location = "北京"
                for i in range(self.days):
                    day = today + timedelta(days=i)
                    bFind = False
                    for iter in range(0,len(old_calendar)):
                        if day.strftime('%Y-%m-%d') == old_calendar[iter]["date"]:
                            bFind = True
                            break
                    if not bFind:
                        print("---------------------NewDay: "+day.strftime('%Y-%m-%d') + "---------------------")
                        self.calendar.append({
                                "date": day.strftime('%Y-%m-%d'),
                                "weekday": self.weekday_map[day.weekday()],
                                "morning": self._fill_period(day,"morning"),
                                "afternoon": self._fill_period(day,"afternoon"),
                                "evening": self._fill_period(day,"evening"),
                        })
                    

                #旧日历和新日历合并&日期排序
                iter2Num = len(self.calendar)
                for iter in range(0,len(old_calendar)):
                    bFind = False
                    for iter2 in range(0,iter2Num):
                        if old_calendar[iter]["date"] == self.calendar[iter2]["date"]:
                            self.calendar[iter2] = old_calendar[iter]
                            bFind = True
                            break
                    if not bFind:
                        self.calendar.append(old_calendar[iter])
                self.calendar = sorted(self.calendar, key=lambda x: x["date"]) # 保证日期排序
                
                #加载日历，顺便更新当天的天气
                self.Update_Weather(isCurrent=False)

                #输出为新日历
                self.save_calendar()
                print(f"🆕 新建/更新公共日历: {self.path}")

    
    
    def Combine_Pub_Use_cal(self,pub_cal_item,user_cal_item):
        if pub_cal_item["date"] == user_cal_item["date"]:
            new_cal_item = pub_cal_item
            time_slots = ["morning","afternoon","evening"]
            for time_slot in time_slots:
                new_cal_item[time_slot]["task_reminder"] = user_cal_item[time_slot]["task_reminder"]
                new_cal_item[time_slot]["user_task"] = user_cal_item[time_slot]["user_task"]

            return new_cal_item       
        else:
            print(f'{self.agent.username}合并日历出现问题，pub_cal_item[\"date\"]:{pub_cal_item["date"]},user_cal_item[\"date\"]:{user_cal_item["date"]}')
            return None
    
    def Syns_calender(self):  #复制公共日历，更新当日天气
        # 打开公共日历
        public_calendar = []
        if os.path.exists(self.path): 
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    public_calendar = json.load(f)
            except Exception as e:
                print(f"⚠️ 公共日历读取失败：{self.path}, 错误: {e}")
        
        if public_calendar:
            for i in range(0,len(public_calendar)):
                day = public_calendar[i]["date"]
                bFind = False
                bCopy = False
                iter_user = 0
                for iter in range(0,len(self.calendar)):
                    iter_user = iter
                    if day == self.calendar[iter]["date"]:
                        if ("is_Pre" not in self.calendar[iter]["morning"]) or (not self.calendar[iter]["morning"]["is_Pre"]):
                            bFind = True
                            bCopy = False
                        else:
                            bFind = True
                            bCopy = True
                        break
                if not bFind: # 复制进入calendar中
                    self.calendar.append(public_calendar[i])
                else:
                    if not bCopy:
                        # 合并内容
                        new_cal_item = self.Combine_Pub_Use_cal(public_calendar[i],self.calendar[iter_user])
                        if new_cal_item != None:
                            self.calendar[iter_user] = new_cal_item # 重新赋值
                            
            self.calendar = sorted(self.calendar, key=lambda x: x["date"]) # 保证日期排序

        self.save_calendar()
        print(f"🆕 新建/更私人日历: {self.username}")
    
    def save_calendar(self):
        json_str = json.dumps(self.calendar, ensure_ascii=False, indent=2)
        json_str = re.sub(
            r'\[\s*((?:[^\[\]]|\n)+?)\s*\]',
            lambda m: '[' + ' '.join(m.group(1).replace('\n', '').split()) + ']',
            json_str
        )
        if self.agent.agent_name != None:
            calendarpath = os.path.join(self.AgentCalendarList,f"Calendar_{self.default_agent_name}.json")
            with open(calendarpath,"w",encoding="utf-8") as f:
                    f.write(json_str)
        else:
            if self.username == None:
                with open(self.path, "w", encoding="utf-8") as f:
                    f.write(json_str)
            # else:  # 多人情况下单独存储
            #     calendarpath = os.path.join(self.CalendarList,f"Calendar_{self.username}.json")
            #     with open(calendarpath,"w",encoding="utf-8") as f:
            #         f.write(json_str)


    def reload_public_calendar(self):
        self.calendar = []
        self._init_calendar()
        self.agent.gen_calender()
        #生成新内容后，顺便更新当天的天气
        self.Update_Weather(isCurrent=False)
    
    # def regit_public_calendar(self):
    #     git_pull()
    #     git_calendar = []
    #     if os.path.exists(self.path):
    #         try:
    #             with open(self.path, "r", encoding="utf-8") as f:
    #                 git_calendar = json.load(f)
    #         except Exception as e:
    #             print(f"⚠️ 日历读取失败：{self.path}, 错误: {e}")
    #             git_calendar = []
    #     print(f"🆕 git成功拉取公共日历: {self.path}")
    #     self.calendar = []
    #     self.calendar = git_calendar
        
        
    # ==== 喜好拓展 ==== #
    def task_details_expand_user_favorite(self, prompt_file, input_info, user_favorite):
        print("582"+self.agent.model_name)
        LLM_Model = LLM_interface.LLM_interface(self.agent.DIALOG_DEEP_SEEK,self.agent.model_name)
        
        message = [{"role": "system", "content": "判断基础内容中是否涉及了“聊天/娱乐”。根据上述判断，输出“Yes”，或“No”"}]
        message.append({
                "role": "system",
                "content": "基本信息:" + input_info
            })
        res = LLM_Model.dialog(message,0.3)

        if 'Yes' in res:
            message = [{"role": "system", "content": self.load_prompt(prompt_file)}]
            msg = "基本信息:" + input_info + ";我的喜好:" + user_favorite
            message.append({
                "role": "system",
                "content": msg
            })
            res = LLM_Model.dialog(message,0.3)
            res = res.replace('\n', '').replace('\r', '')
            return res
        return input_info.replace('\n', '').replace('\r', '')

    # ==== 根据不同的prompt_file提示，扩展细节信息，目前只返回内容str ==== #
    def task_details_expand(self, calendar, day_index, time_slot, prompt_file, input_info, holidayInfo = True, weatherInfo = True, friends = []):
        task_info = ''
        if holidayInfo:
            task_info += f"节假日：{calendar[day_index][time_slot].get('holiday', '')}\n"
        if weatherInfo:
            task_info += f"天气：{calendar[day_index][time_slot].get('weather', '')}\n"
        task_info += f"现在时间：生成 {calendar[day_index]['date']} ({calendar[day_index]['weekday']}) [{time_slot}(生成的内容在逻辑上要符合时间特点)]"
        task_info += "基本信息:" + input_info

        print("614"+self.agent.model_name)
        LLM_Model = LLM_interface.LLM_interface(self.agent.DIALOG_DEEP_SEEK,self.agent.model_name)
        message = [{"role": "system", "content": self.load_prompt(prompt_file)}]
        message.append({
                "role": "system",
                "content": task_info
            })
        res = LLM_Model.dialog(message)
        return res.replace('\n', '').replace('\r', '')
    
    # ==== 根据事件细节内容，总结信息 ==== #
    def fill_task_summary(self, task_detail):
        print("fill_task_summary:" + task_detail)
        if len(task_detail)==0:
            return ""
        print("629"+self.agent.model_name)
        LLM_Model = LLM_interface.LLM_interface(self.agent.DIALOG_DEEP_SEEK,self.agent.model_name)
        prompt_str = f"请将输入的内容(内容是关于'{self.default_agent_name}自己/和用户发生的事情')概括成一句简洁客观的总结,不超过20个字.输出格式为:'{self.default_agent_name}xxxx'" + task_detail
        sys_msg = [{
                "role": "system",
                "content": prompt_str
            }]
        
        res = LLM_Model.dialog(sys_msg,0.3)
        print("fill_task_summary_result:" + res)
        return res
    
    def fill_task_details(self, calendar, day_index, time_slot, prompt_file, task_planning = None, gender = "男", bio_energy = 1.0, task_planning_score = 0.5, task_result = None, holidayInfo = True, weatherInfo = True, friends = []):
        print("642"+self.agent.model_name)
        LLM_Model = LLM_interface.LLM_interface(self.agent.DIALOG_DEEP_SEEK,self.agent.model_name)

        message = [{"role": "user", "content": self.load_prompt(prompt_file)}]
        task_info = ""
        task_info += f"外部事件：{calendar[day_index][time_slot].get('world_plan', '')}\n"

        # ==== 根据采样得分判断期待值 ==== #
        task_expect = ""
        if task_planning_score < 0.7:
            task_expect = "(一般期待)"
        elif task_planning_score < 0.8:
            task_expect = "(比较期待)"
        elif task_planning_score < 0.9:
            task_expect = "(很期待)"
        elif task_planning_score < 1.1:
            task_expect = "(非常期待)"
        else:
            task_expect = "(超级期待)"

        task = ''
        if not task_planning == None:
            task = f"计划执行的事件：【{task_planning}{task_expect}】\n"
        # 加入事件的运行结果：
        if not task_result == None:
            task += f"实际执行的事件获得的效果是：【{task_result}】"    
        if len(friends) > 0:
            task += f"你的伙伴包括:"
            for item in friends:
                task += item
            task += f"根据事件的内容，选择最合适的伙伴加入到叙事内容里。\n"
        task_info += task

        if holidayInfo:
            task_info += f"节假日：{calendar[day_index][time_slot].get('holiday', '')}\n"
        if weatherInfo:
            task_info += f"天气：{calendar[day_index][time_slot].get('weather', '')}\n"
        
        msg = (f"现在时间：生成 {calendar[day_index]['date']} ({calendar[day_index]['weekday']}) [{time_slot}(生成的内容在逻辑上要符合时间特点)]"
                + task_info
                + f"人物状态：性别---{gender},体力--{str(bio_energy)}"
                + "只返回task_detail文字内容即可")
        message.append({
            "role": "system",
            "content": msg
        })
        
        #print(message)
        res = LLM_Model.dialog(message)

        rp = ['\n','\r',' ','任务详情','task_details',':','：','任务完成']
        for item in rp:
           res = res.replace(item,'') 
        return res

    def prepare_calendar(self, day_index, time_slot):  # 如果内容已有，就不再重新选择
        #calendar = self.get_calendar_from_file()
        if ("is_Pre" not in self.calendar[day_index][time_slot]) or (not self.calendar[day_index][time_slot]["is_Pre"]):
            if not (0 <= day_index < len(self.calendar)):
                print("❌ 天数超范围！")
                return
            if time_slot not in ['morning', 'afternoon', 'evening']:
                print("❌ 时段必须是 morning/afternoon/evening")
                return
            #print(self.calendar[day_index][time_slot]['weather'] + ",节假日:" + self.calendar[day_index][time_slot]['holiday'])
            # ==== 外部事件内容生成 ==== #
            # if self.world_plan and isinstance(self.world_plan,dict):
            #     world_plan_list = self.world_plan.get(self.calendar[day_index]["date"],"无")
            #     if world_plan_list != '无':
            #         if isinstance(world_plan_list,list):
            #             for item in world_plan_list:
            #                 if item["period"] == time_slot:
            #                     self.calendar[day_index][time_slot]["world_plan"] = item["plan"]
            #                     status = item.get("status",'')
            #                     if status:
            #                         self.calendar[day_index][time_slot]["status"] = status

            # ==== life_style_weight权重生成 ==== # 
            # if self.calendar[day_index][time_slot]["life_style_weight"] == [1.0,1.0,1.0,1.0,1.0]: # 已有权重，那就不再生成
            #     matched_ranges = self.agent.external_event_manager.get_matching_social_phases_macro(self.calendar[day_index]["date"],self.calendar[day_index]["weekday"])
            #     keys = ["生理", "工作", "休闲", "社交", "情感"]
            #     life_style_weight = [1.0,1.0,1.0,1.0,1.0]
            #     for idx, influence_range in enumerate(matched_ranges):
            #         for i, key in enumerate(keys):
            #             low, high = influence_range[key]
            #             delta = random.uniform(low, high)
            #             life_style_weight[i] += delta
            #     self.calendar[day_index][time_slot]["life_style_weight"] = [round(w, 3) for w in life_style_weight]

            #print(f"🚩{self.calendar[day_index]['date']}{time_slot}的life_style_weights:生理🍔 {self.calendar[day_index][time_slot]['life_style_weight'][0]},工作✍  {self.calendar[day_index][time_slot]['life_style_weight'][1]},休闲⚽ {self.calendar[day_index][time_slot]['life_style_weight'][2]},社交🗯  {self.calendar[day_index][time_slot]['life_style_weight'][3]},情感💕 {self.calendar[day_index][time_slot]['life_style_weight'][4]}")
            #print(f"🚩体力值:{self.agent.bio_energy}")
            # ==== 外部事件响应 ==== #
            status = self.calendar[day_index][time_slot]["status"]
            if status == "" or status == "random_plan":
                # ===========外部事件处理=========== #
                # if not self.calendar[day_index][time_slot]["world_plan"] == "":
                #     #print("外部事件进入事件池")
                #     world_plan = self.calendar[day_index][time_slot]["world_plan"]
                #     #print(world_plan)
                #     self.agent.external_event_manager.External_event_to_Action(world_plan,time_slot) #对外部事件进行动作映射

                # ========== 随机活动选择 ========== #
                if self.calendar[day_index][time_slot]['task_planning'] == "": # 已有活动，就不再进行选择
                    life_style_weight = self.calendar[day_index][time_slot]['life_style_weight'] # 日程活动倾向影响
                    result = self.agent.select_best_behavior(top_k=2, current_Time_slot=time_slot,life_style_weight = life_style_weight)
                    if result[0]:
                        behavior_info = result[0]
                        #print(f"🕒 {time_slot.upper()}: {behavior_info['behavior_detail']}")
                        self.calendar[day_index][time_slot]["task_planning"] = behavior_info["behavior_detail"] #这里是不包括执行效果的
                        self.calendar[day_index][time_slot]["task_planning_score"] = float(behavior_info["score"])
                        self.calendar[day_index][time_slot]['task_result'] = behavior_info['behavior_result']
                    else:
                        print(f"⚠️ {time_slot.upper()} 当前时段无可选行为")
                # else:
                #     task_planning,task_result = self.agent._apply_behavior(self.calendar[day_index][time_slot]['task_planning'], self.agent.luck)
                #     self.calendar[day_index][time_slot]['task_result'] = task_result
                #     #print(f"🕒 {time_slot.upper()}: {self.calendar[day_index][time_slot]['task_planning']}")
                #     pass
            
            # elif status == "long-term-plan":
            #     # ===========外部事件处理=========== #
            #     # if not self.calendar[day_index][time_slot]["world_plan"] == "":
            #     #     #print("外部事件进入事件池")
            #     #     world_plan = self.calendar[day_index][time_slot]["world_plan"]
            #     #     #print(world_plan)
            #     #     self.agent.external_event_manager.External_event_to_Action(world_plan,time_slot) #对外部事件进行动作映射

            #     # ========== 随机活动选择 ========== #
            #     if self.calendar[day_index][time_slot]['task_planning'] == "": # 已有活动，就不再进行选择
            #         life_style_weight = self.calendar[day_index][time_slot]['life_style_weight'] # 日程活动倾向影响
            #         result = self.agent.select_best_behavior(top_k=2, current_Time_slot=time_slot,life_style_weight = life_style_weight,is_long_term_plan = True)
            #         if result[0]:
            #             behavior_info = result[0]
            #             #print(f"🕒 {time_slot.upper()}: {behavior_info['behavior_detail']}")
            #             self.calendar[day_index][time_slot]["task_planning"] = behavior_info["behavior_detail"] #这里是不包括执行效果的
            #             self.calendar[day_index][time_slot]["task_planning_score"] = float(behavior_info["score"])
            #             self.calendar[day_index][time_slot]["task_result"] = behavior_info['behavior_result']
            #         else:
            #             print(f"⚠️ {time_slot.upper()} 当前时段无可选行为")
            #     else:
            #         task_planning,task_result = self.agent._apply_behavior(self.calendar[day_index][time_slot]['task_planning'], self.agent.luck)
            #         self.calendar[day_index][time_slot]['task_result'] = task_result
            #         #print(f"🕒 {time_slot.upper()}: {self.calendar[day_index][time_slot]['task_planning']}")
            #         pass

            # ========== 日历更新Avatar状态值 ========== # 移到了play当中，play才是真实情况
            self.calendar[day_index][time_slot]['avatar_bio_energy'] = float(self.agent.bio_energy)
            self.calendar[day_index][time_slot]['avatar_mood_valence'] = float(self.agent.emotion_module.valence)
            self.calendar[day_index][time_slot]['avatar_mood_arousal'] = float(self.agent.emotion_module.arousal)
            self.calendar[day_index][time_slot]['avatar_luck'] = float(self.agent.luck)
            self.calendar[day_index][time_slot]['avatar_behavior_fatigue'] = self.agent.behavior_fatigue
            
            #外部事件库根据时间流逝更新
            #self.agent.external_event_manager.Updata_External_Event()
            self.calendar[day_index][time_slot]["is_Pre"] = True
        else:
            self.agent.bio_energy = self.calendar[day_index][time_slot]['avatar_bio_energy']
            self.agent.emotion_module.valence = self.calendar[day_index][time_slot]['avatar_mood_valence']
            self.agent.emotion_module.arousal = self.calendar[day_index][time_slot]['avatar_mood_arousal']
            #self.agent.luck = self.calendar[day_index][time_slot]['avatar_luck']
            self.agent.behavior_fatigue = self.calendar[day_index][time_slot]['avatar_behavior_fatigue']
        
        self.save_calendar()
        

    def play_calendar(self,day_index, time_slot):
        """第二遍遍历calendar,生成真实活动"""
        if ("is_Play" not in self.calendar[day_index][time_slot]) or (not self.calendar[day_index][time_slot]["is_Play"]): 
            # ==== 天气、假期信息 ==== #
            holidayInfo = True
            if random.random()<0.6: 
                holidayInfo = False
            weatherInfo = True
            if random.random()<0.2:
                weatherInfo = False

            #print(self.calendar[day_index][time_slot]['weather'] + ",节假日:" + self.calendar[day_index][time_slot]['holiday'])
            task_planning = self.calendar[day_index][time_slot]["task_planning"]
            task_planning_score = self.calendar[day_index][time_slot]["task_planning_score"]
            task_result = self.calendar[day_index][time_slot]['task_result']

            #print(f"🕒 {time_slot.upper()}计划事件: {task_planning}")

            # ==== 判断是否要提供未来事件 ==== #
            if 1:
                future_day = 0
                future_slot = 0
                future_score = 0
                
                time_slot_index = {"morning": 0, "afternoon": 1, "evening": 2}
                reverse_time_slot = ["morning", "afternoon", "evening"]

                # ==== 判断是否要加入对未来的期待 ==== #
                current_global_index = day_index * 3 + time_slot_index[time_slot]
                if random.random()<0.8:# 按照期待值还是随机选择
                    #print("按照期待度最大化选择未来事件")
                    future_score_max = 0.0
                    future_day_max = 0
                    futrue_slot_max = ""
                    for iter in range(1,6+2-time_slot_index[time_slot]): # 至少2天，最多2+2个当日阶段
                        future_global_index = current_global_index + iter
                        if future_global_index < len(self.calendar)*3:
                            future_day = future_global_index // 3
                            future_slot = reverse_time_slot[future_global_index % 3]
                            future_score = float(self.calendar[future_day][future_slot]["task_planning_score"])
                            if future_score > future_score_max:
                                future_day_max = future_day
                                futrue_slot_max = future_slot
                                future_score_max = future_score
                    future_day = future_day_max
                    future_slot = futrue_slot_max
                    future_score = future_score_max
                else:
                    #print("执行随机选择未来事件")
                    future_global_index = min(len(self.calendar)*3-1,current_global_index + random.randint(1,9+2-time_slot_index[time_slot]))
                    future_day = future_global_index // 3
                    future_slot = reverse_time_slot[future_global_index % 3]
                    future_score = float(self.calendar[future_day][future_slot]["task_planning_score"])

                if future_score > task_planning_score - 0.3:
                    delta_score = future_score - task_planning_score
                    if random.random() > delta_score + float(time_slot_index[time_slot])*0.3:
                        pass
                    else:
                        #根据是否喜欢做这件事来决定期待值:
                        task_planning = self.calendar[future_day][future_slot]['task_planning']
                        value = future_score
                        if "(非常喜欢做)" in task_planning:
                            value = value + 0.1
                        elif "(很喜欢做)" in task_planning:
                            value = value + 0.05
                        elif "(喜欢做)" in task_planning:
                            value = value
                        elif "(不喜欢做)" in task_planning:
                            value = value - 0.1
                        elif "(讨厌做)" in task_planning:
                            value = value - 0.15
                        value = max(0.0,value)
                        self.calendar[future_day][future_slot]["task_planning_score"] = value #增加对未来具体事情的期待
                
            if 1:
                # ==== 判断是否要重新对当前事件进行选择 ==== #
                # 用体力、精力、情绪（喜好）等判断，如果不符合则re_select=1
                re_select = max(0.0,1.0 - self.calendar[day_index][time_slot]["task_planning_score"]) * 2.0
                if random.random() < re_select: # 选择了新的内容
                    task_result = "正常"
                    # =========== 外部事件处理 =========== #
                    if not self.calendar[day_index][time_slot]["world_plan"] == "":
                        world_plan = self.calendar[day_index][time_slot]["world_plan"]
                        #print("外部事件："+world_plan)
                        self.agent.external_event_manager.External_event_to_Action(world_plan,time_slot) # 对外部事件进行动作映射

                    # =========== 随机活动选择 =========== #
                    life_style_weight = self.calendar[day_index][time_slot]["life_style_weight"] # 日程活动倾向影响
                    if self.calendar[day_index][time_slot]["status"] != "long-term-plan":
                        result = self.agent.select_best_behavior(top_k=2, current_Time_slot=time_slot,life_style_weight = life_style_weight)
                    else:
                        result = self.agent.select_best_behavior(top_k=2, current_Time_slot=time_slot,life_style_weight = life_style_weight,is_long_term_plan = True)
                    if result[0]:
                        behavior_info = result[0]
                        self.calendar[day_index][time_slot]["task_planning"] = behavior_info["behavior_name"]
                        task_result = behavior_info["behavior_result"]
                        self.calendar[day_index][time_slot]['task_result'] = behavior_info['behavior_result'] # 重新选择后，结果直接覆盖即可
                        if behavior_info["behavior_detail"] in self.calendar[day_index][time_slot]['task_planning'] or self.calendar[day_index][time_slot]['task_planning'] in behavior_info["behavior_detail"]:
                            task_planning = task_planning + "(结果:" + behavior_info["behavior_result"] + ")"
                    else:
                        print(f"⚠️ {time_slot.upper()} 当前时段无可选行为")
                else:
                    # =========== 执行当前规划 =========== #
                    task_planning = self.calendar[day_index][time_slot]['task_planning']
                    task_result = self.calendar[day_index][time_slot]['task_result']
                    task_planning = task_planning + "(结果:" + task_result + ")"
                    self.agent.bio_energy = self.calendar[day_index][time_slot]['avatar_bio_energy']
                    self.agent.emotion_module.valence = self.calendar[day_index][time_slot]['avatar_mood_valence']
                    self.agent.emotion_module.arousal = self.calendar[day_index][time_slot]['avatar_mood_arousal']
                    self.agent.behavior_fatigue = self.calendar[day_index][time_slot]['avatar_behavior_fatigue']

            # ========== 日历更新Avatar状态值 ========== # 移到了play当中，play才是真实情况
            self.calendar[day_index][time_slot]['avatar_bio_energy_play'] = float(self.agent.bio_energy)
            self.calendar[day_index][time_slot]['avatar_mood_valence_play'] = float(self.agent.emotion_module.valence)
            self.calendar[day_index][time_slot]['avatar_mood_arousal_play'] = float(self.agent.emotion_module.arousal)
            self.calendar[day_index][time_slot]['avatar_luck'] = float(self.agent.luck)
            self.calendar[day_index][time_slot]['avatar_behavior_fatigue_play'] = self.agent.behavior_fatigue
                
            # ==== 判断是否要回忆 ==== #
            

            # ==== 生成详细内容 ==== #
            task_prompt_file = None
            if self.default_agent_name == "狐狐":

                task_prompt_file = "Fill_Task_Detail_With_Appearance_HuHu.txt"
            else: # default 小白
                if random.random()<0.5:# Prompt里有外貌信息
                    task_prompt_file = "Fill_Task_Detail_With_Appearance.txt"
                else:# Prompt里无外貌信息
                    task_prompt_file = "Fill_Task_Detail_No_Appearance.txt"    
                if (not task_planning == None and "共情交流" in task_planning):
                    #与用户共情沟通，主动发起一个话题
                    task_prompt_file = "Fill_Task_Empathy_With_User.txt"


            friends = []# 朋友暂时清空

            # 当前事件的内容文案生成
            if self.calendar[day_index][time_slot]["task_details"] == "":
                task_detail = self.fill_task_details(
                    self.calendar, day_index, time_slot, 
                    task_prompt_file, 
                    gender = self.agent.user_gender,
                    bio_energy = self.agent.bio_energy,
                    task_planning = task_planning, 
                    task_planning_score = task_planning_score, 
                    task_result = task_result,
                    holidayInfo = holidayInfo, 
                    weatherInfo = weatherInfo, 
                    friends = friends
                    )
            else:
                task_detail = self.calendar[day_index][time_slot]["task_details"]
            self.calendar[day_index][time_slot]["task_details"] = task_detail

            # 事件总结
            task_prompt = ""
            if self.calendar[day_index][time_slot]["task_prompt"] == "":
                task_prompt = self.fill_task_summary(task_detail)
            else:
                task_prompt = self.calendar[day_index][time_slot]["task_prompt"]

            if task_prompt == None:
                self.calendar[day_index][time_slot]["task_prompt"] = ""
            else:
                self.calendar[day_index][time_slot]["task_prompt"] = task_prompt
            
            self.calendar[day_index][time_slot]["is_Play"] = True

            #print("\n")
        else:

            if len(self.calendar[day_index][time_slot]["task_prompt"]) == 0:
                self.calendar[day_index][time_slot]["task_prompt"] = self.fill_task_summary(self.calendar[day_index][time_slot]["task_details"])

            self.agent.bio_energy = self.calendar[day_index][time_slot]['avatar_bio_energy_play']
            self.agent.emotion_module.valence = self.calendar[day_index][time_slot]['avatar_mood_valence_play']
            self.agent.emotion_module.arousal = self.calendar[day_index][time_slot]['avatar_mood_arousal_play']
            #self.agent.luck = self.calendar[day_index][time_slot]['avatar_luck']
            self.agent.behavior_fatigue = self.calendar[day_index][time_slot]['avatar_behavior_fatigue_play']


    def show(self, day_index=None):
        if day_index is None:
            for idx, day in enumerate(self.calendar):
                print(f"{idx}: {day['date']} {day['weekday']}")
        else:
            print(json.dumps(self.calendar[day_index], ensure_ascii=False, indent=2))
    
    def load_prompt(self,filename: str) -> str:
        file_path = f'prompt_zh/{filename}'
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()
        except:
            print(f"{filename}读取失败")
            system_prompt = ""
        return system_prompt
    
    def get_agent_event_summary(self, today, current_hour):
        '''这个函数依赖于Calendar按照时间顺序排列，要保证Calendar时间顺序正确'''
        history_event_summary = ''
        current_event_summary = ''
        current_event_summary_short = ''
        future_event_summary = ''

        if current_hour < 6:
            today = today - timedelta(days=1)

        calendar = self.calendar
        # ==== 过去事件的相关记忆==== #     
  
        #从日历中选择出过去的事件 history_event_summary，并获得当下时间的简洁版和详情版
        if not calendar == None:
            time_index_container = [0,0]
            reverse_time_slot = ["morning", "afternoon", "evening"]
            reverse_time_str = ["上午", "下午", "晚上"]
            for idx, item in enumerate(calendar):
                if item['date'] == today.isoformat():
                    time_index_container[0] = idx
                    break
            day_index = time_index_container[0]
            # 判断当前时间属于哪个时段
            if 6 <= current_hour < 12:
                time_slot = 0  # 早上
            elif 12 <= current_hour < 18:
                time_slot = 1  # 中午
            else:
                time_slot = 2  # 晚上

            for index in range(-2,1):  # -2, -1, 0
                _day_index = day_index + index
                if _day_index >= 0 and _day_index < len(calendar): 
                    for _time_slot in range(0,3):
                        if index == 0:
                            if _time_slot > time_slot:
                                break
                            elif _time_slot == time_slot:
                                current_event_summary += calendar[_day_index][reverse_time_slot[_time_slot]]['task_details'] # 获得当天的行为内容详情
                                current_event_summary_short += calendar[_day_index][reverse_time_slot[_time_slot]]['task_prompt'] # 当天的行为简洁版
                                break
                        summary_message = calendar[_day_index][reverse_time_slot[_time_slot]]['task_prompt'] # 先前的行为简洁版
                        if len(summary_message)> 0:
                            date_str = ""
                            if index == -2:
                                date_str = '前天'
                            elif index == -1:
                                date_str = '昨天'
                            elif index == 0:
                                date_str = '今天'
                            summary = f"{date_str}{reverse_time_str[_time_slot]}:{summary_message};"
                            history_event_summary += summary

        # ==== 近期的规划 ==== #
        #从日历中选择出对未来期待度最大的事件
        if not calendar == None:
            time_index_container = [0,0]
            reverse_time_slot = ["morning", "afternoon", "evening"]
            reverse_time_str = ["上午", "下午", "晚上"]
            # 获取当前时间
            current_hour = datetime.now().hour
            today = datetime.now().date().isoformat()
            for idx, item in enumerate(calendar):
                if item['date'] == today:
                    time_index_container[0] = idx
                    break
            day_index = time_index_container[0]
            # 判断当前时间属于哪个时段
            if 6 <= current_hour < 12:
                time_slot = 0  # 早上
            elif 12 <= current_hour < 18:
                time_slot = 1  # 中午
            else:
                time_slot = 2  # 晚上

            for index in range(0,3):  # 0，1，2
                _day_index = day_index + index
                if _day_index >= 0 and _day_index < len(calendar): 
                    for _time_slot in range(0,3):
                        if index == 0:
                            if _time_slot <= time_slot:
                                break
                        value = float(calendar[_day_index][reverse_time_slot[_time_slot]]["task_planning_score"])
                        if value > 2.0:
                            if len(calendar[_day_index][reverse_time_slot[_time_slot]]['task_planning'])>0:
                                date_str = ""
                                if index == 0:
                                    date_str = '今天'
                                elif index == 1:
                                    date_str = '明天'
                                elif index == 2:
                                    date_str = '后天'
                                action = calendar[_day_index][reverse_time_slot[_time_slot]]['task_planning']
                                pattern = r'【(.*?)】'
                                matches = re.findall(pattern, action)
                                if len(matches)>0:
                                    action = matches[0]
                                    action = action.replace('【','').replace('】','').replace('[','').replace(']','')
                                if "-" in action:
                                    action = action.split('-')[1]
                                proactive_system = f"{date_str}{reverse_time_str[_time_slot]}:{action}"
                                future_event_summary += proactive_system
        history_event_summary = history_event_summary.replace("\\n","\n")
        current_event_summary = current_event_summary.replace("\\n","\n")
        current_event_summary_short = current_event_summary.replace("\\n","\n")
        future_event_summary = future_event_summary.replace("\\n","\n")
        return history_event_summary,current_event_summary,current_event_summary_short,future_event_summary