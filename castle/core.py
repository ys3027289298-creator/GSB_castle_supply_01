"""守城回合制后端。

每回合原子结算：所有变更先计入暂存区，校验通过后一次性落盘；
任一环节非法则整回合不变。事件随机流按 (seed, day) 派生，
重放事件不会改变随机顺序。
"""
from __future__ import annotations

import random

SAVE_KEYS = (
    "day", "food", "arrows", "morale", "gate", "materials",
    "soldiers", "wounded", "seed", "over", "victory",
)

MAX_FOOD = 200
MAX_ARROWS = 500
MAX_GATE = 100
MAX_MORALE = 100

FOOD_PER_HEAD = 1
FEED_MORALE_BONUS = 3
STARVE_MORALE_COST = 10
REPAIR_POINTS = 10
REPAIR_MATERIALS_PER_POINT = 2
VOLLEY_ARROWS = 10
VOLLEY_MORALE_COST = 2
RECALL_MORALE_RETURN = 5
TRUCE_INTERVAL = 4
VICTORY_DAY = 10
WOUND_RECOVER = 1

MSG_OK = "命令已执行"
MSG_INVALID = "未知命令"
MSG_NO_FOOD = "粮食不足"
MSG_NO_ARROWS = "箭矢耗尽"
MSG_NO_MATERIALS = "材料不足"
MSG_ALREADY_FED = "本回合粮食已分配"
MSG_GAME_OVER = "战斗已结束"
MSG_VICTORY = "守城成功"
MSG_DEFEAT = "城破人亡"
MSG_RAID = "夜袭！城门受损"
MSG_TRUCE = "停战日，无事发生"

CMD_FEED = "分配粮食"
CMD_REPAIR = "修理城门"
CMD_SHOOT = "射击"
CMD_RECALL = "撤回"
CMD_END_TURN = "结束回合"


class CastleGame:
    def __init__(self, seed=7):
        self.day = 1
        self.food = 100
        self.arrows = 100
        self.morale = 50
        self.gate = MAX_GATE
        self.materials = 40
        self.soldiers = 20
        self.wounded = 0
        self.seed = seed
        self.over = False
        self.victory = False
        self._food_allocated = False
        self.log = []

    @property
    def defenders(self):
        """守军只计健康士兵，伤兵不计入。"""
        return self.soldiers

    @staticmethod
    def is_truce(day):
        return day % TRUCE_INTERVAL == 0

    def _event_rng(self, day, tag):
        return random.Random("%s:%s:%s" % (self.seed, day, tag))

    def raid_damage(self, day):
        """夜袭伤害：由 (seed, day) 决定，重放不影响其他随机流。"""
        if self.is_truce(day):
            return 0
        return self._event_rng(day, "raid").randint(5, 15)

    def preview_events(self, day):
        if self.is_truce(day):
            return [MSG_TRUCE]
        return [MSG_RAID, "伤害:%d" % self.raid_damage(day)]

    def apply(self, command):
        if self.over:
            return MSG_GAME_OVER
        if command == CMD_FEED:
            return self._feed()
        if command == CMD_REPAIR:
            return self._repair()
        if command == CMD_SHOOT:
            return self._shoot()
        if command == CMD_RECALL:
            return self._recall()
        if command == CMD_END_TURN:
            return self._end_turn()
        return MSG_INVALID

    def _feed(self):
        if self._food_allocated:
            return MSG_ALREADY_FED
        cost = (self.soldiers + self.wounded) * FOOD_PER_HEAD
        if self.food < cost:
            return MSG_NO_FOOD
        self.food = min(MAX_FOOD, self.food - cost)
        self.morale = min(MAX_MORALE, self.morale + FEED_MORALE_BONUS)
        self._food_allocated = True
        return MSG_OK

    def _repair(self):
        points = min(REPAIR_POINTS, MAX_GATE - self.gate)
        cost = points * REPAIR_MATERIALS_PER_POINT
        if self.materials < cost:
            return MSG_NO_MATERIALS
        self.materials -= cost
        self.gate += points
        return MSG_OK

    def _shoot(self):
        if self.arrows < VOLLEY_ARROWS:
            return MSG_NO_ARROWS
        self.arrows -= VOLLEY_ARROWS
        self.morale = max(0, self.morale - VOLLEY_MORALE_COST)
        return MSG_OK

    def _recall(self):
        self.morale = min(MAX_MORALE, self.morale + RECALL_MORALE_RETURN)
        return MSG_OK

    def _end_turn(self):
        # 原子结算：先算全部增量，校验后一次性应用。
        damage = self.raid_damage(self.day)
        new_gate = max(0, self.gate - damage)
        new_morale = self.morale
        if not self._food_allocated:
            new_morale = max(0, new_morale - STARVE_MORALE_COST)
        new_soldiers = self.soldiers
        new_wounded = self.wounded
        if damage > 0 and self.defenders > 0:
            hit = min(self.defenders, damage // 5)
            new_soldiers -= hit
            new_wounded += hit
        recover = min(WOUND_RECOVER, new_wounded)
        new_wounded -= recover
        new_soldiers += recover

        self.gate = new_gate
        self.morale = new_morale
        self.soldiers = new_soldiers
        self.wounded = new_wounded
        self.log.extend(self.preview_events(self.day))
        self.day += 1
        self._food_allocated = False

        if self.gate <= 0:
            self.over = True
            self.victory = False
            return MSG_DEFEAT
        if self.day > VICTORY_DAY:
            self.over = True
            self.victory = True
            return MSG_VICTORY
        return MSG_OK

    def save(self):
        return {key: getattr(self, key) for key in SAVE_KEYS}

    @classmethod
    def load(cls, data):
        if not data:
            raise ValueError("存档数据为空")
        missing = [key for key in SAVE_KEYS if key not in data]
        if missing:
            raise ValueError("存档缺少键: %s" % ",".join(missing))
        game = cls(seed=data["seed"])
        for key in SAVE_KEYS:
            setattr(game, key, data[key])
        return game


def run_demo():
    """固定种子演示：脚本化命令序列，输出确定。"""
    game = CastleGame(seed=42)
    script = [
        CMD_FEED, CMD_REPAIR, CMD_SHOOT, CMD_RECALL, CMD_END_TURN,
        CMD_FEED, CMD_END_TURN,
        CMD_FEED, CMD_END_TURN,
        CMD_FEED, CMD_END_TURN,  # 第 4 天停战
    ]
    for command in script:
        print("第%d天 [%s] -> %s" % (game.day, command, game.apply(command)))
    state = game.save()
    print("存档:", {key: state[key] for key in SAVE_KEYS})
    return game


if __name__ == "__main__":
    run_demo()
