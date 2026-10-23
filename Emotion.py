import re
import numpy as np

class EmotionState:
    def __init__(self, personality_vector, emotional_vector):
        self.init_emotion = emotional_vector
        self.valence = emotional_vector[0]  # 当前的情绪效价（范围 -1.0 ~ 1.0), -1 表示极端负面情绪（如沮丧、愤怒）+1 表示极端正面情绪（如愉悦、兴奋）

        self.arousal = 0.5 # 情绪唤醒值，（范围 0.0 ~ 1.0)

        self.valence_baseline = emotional_vector[1]  # 情绪效价的个体基准线（个性倾向），可用于表示一个人天生偏悲观或乐观（例如 -0.2 表示略偏负面）

        self.valence_decay_rate = emotional_vector[2]  # 情绪回归中性状态的衰减速率，每一次 decay 调用时，valence 会以此比例向 baseline 回落
        
        self.valence_sensitivity = emotional_vector[3]  # 个体对事件刺激的情绪反应强度（放大倍数），值越大 → 对行为结果更敏感，情绪波动更剧烈

        self.personality = personality_vector

        # 从人格中提取目标坚持度，用于调节：行为成败是否强烈影响情绪
        self.goal_sensitivity = personality_vector[5] # psychological_goal_persistence

        # 从人格中提取情绪反应性，用于调节：情绪对刺激的放大程度（包括正面与负面）
        self.emotional_reactivity = personality_vector[3] # psychological_emotional_reactivity

        # 从人格中提取风险规避度，反向计算失败容忍度
        # 越害怕风险，越不能接受失败（所以 1 - 风险规避 = 容忍失败的能力）
        self.failure_tolerance = 1 - personality_vector[4] # psychological_risk_aversion

        # 从人格中提取“社会评价敏感度”，用于调节行为是否涉及形象/面子时的情绪影响
        self.social_feedback_sensitivity = personality_vector[9] # social_self_presentation

        # 从人格中提取探索好奇驱动，用于调节失败后的恢复力
        # 高探索欲的人面对失败容易重建积极情绪，看到失败为“经验”
        self.exploratory_resilience = personality_vector[6] # psychological_curiosity_drive
        
        self.frustration_level = 0.0 # 挫折状态
        self.mood_history = []

    def _estimate_valence_delta(self, behavior, psycho_cunsumption, success_value):
        # 融合估算：行为与人格的匹配 + 成败影响
        weight = np.array(behavior["Weight"])

        # 匹配得分：划分索引
        DIRECT_IDX = [3, 4, 5, 9, 10]
        INDIRECT_IDX = [6, 8, 11]

        direct_match = np.dot(weight[DIRECT_IDX], self.personality[DIRECT_IDX])
        indirect_match = np.dot(weight[INDIRECT_IDX], self.personality[INDIRECT_IDX])

        if success_value > 0.0:
            valence = (
                psycho_cunsumption +
                direct_match * 0.05 +
                indirect_match * 0.02
            )
        else:
            valence = (
                psycho_cunsumption -
                direct_match * 0.07 -
                indirect_match * 0.02
            )

        return valence

    def process_behavior(self, bio_energy, behavior, psycho_cunsumption, success_value):
        # 估算行为的valence影响，并更新当前状态
        valence_delta = self._estimate_valence_delta(behavior, psycho_cunsumption, success_value)
        modulator = self.valence_sensitivity * self.emotional_reactivity * 4.0

        if success_value < 0.0:
            tolerance = np.clip(self.failure_tolerance + self.exploratory_resilience * 0.5, 0.0, 1.0)
            modulator *= (1.0 - tolerance*0.2)
    
        adjustment = valence_delta * modulator
        self.valence += adjustment
        self.valence = np.clip(self.valence,-1.0,1.0)
        self.arousal = np.clip(0.6 * bio_energy + self.emotional_reactivity * self.valence_sensitivity * 0.2, 0.0, 1.0)

        if self.valence < -0.3:
            self.frustration_level += abs(self.valence) * 0.1
        else:
            self.frustration_level *= 0.9

        self.mood_history.append(self.valence)
        if len(self.mood_history)>5:
            self.mood_history.pop(0)

        #print("psycho_cunsumption:" + str(psycho_cunsumption))
        #print("valence_delta:" + str(valence_delta))
        #print("adjustment:" + str(adjustment))
        return 0

    def decay(self):
        self.valence = np.clip(self.valence * (1.0-self.valence_decay_rate) - self.valence_baseline * self.valence_decay_rate,-1.0,1.0)

    def current_mood_valence(self):
        v = self.valence
        if v > 0.6:
            return f"喜悦({v:.2f})"       # 高效价：明显幸福与兴奋
        elif v > 0.4:
            return f"满足({v:.2f})"       # 稍低于喜悦，更沉稳的正面情绪
        elif v > 0.2:
            return f"轻松({v:.2f})"       # 心情良好但非强烈积极
        elif v > -0.4:
            return f"普通({v:.2f})"       # 略偏正，安静平稳
        elif v > -0.5:
            return f"低落({v:.2f})"       # 稍微偏负，尚能调节
        elif v > -0.7:
            return f"消沉({v:.2f})"       # 显著负面，但未失控
        elif v > -0.9:
            return f"烦闷({v:.2f})"       # 情绪压抑，易爆发或内耗
        else:
            return f"沮丧({v:.2f})"       # 极度负面，接近抑郁或崩溃
        
    def current_mood_arousal(self):
        v = self.arousal
        if v > 0.5:
            return f"很强({v:.2f})"       # 极度激活状态，可能是兴奋、紧张、狂喜、焦躁
        elif v > 0.3:
            return f"较强({v:.2f})"       # 精神集中、充满动力，准备行动
        elif v > 0.2:
            return f"正常({v:.2f})"       # 中等唤醒，心情平衡、淡定从容
        elif v > 0.1:
            return f"较弱({v:.2f})"       # 有些困倦，精力低但未完全失控
        else:
            return f"很弱({v:.2f})"       # 极低激活，身心俱疲、难以应对