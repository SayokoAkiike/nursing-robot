"""
ロボット状態遷移 (Day 10)
実行方法: python robot_control/state_machine.py
"""

from enum import Enum, auto
from datetime import datetime
import time


class RobotState(Enum):
    IDLE                          = auto()
    REQUEST_RECEIVED              = auto()
    KIT_SELECTED                  = auto()
    MOVING_TO_BEDSIDE             = auto()
    VERIFYING_PATIENT             = auto()
    DOCKING                       = auto()
    TRAY_LIFTING                  = auto()
    WAITING_FOR_NURSE_CONFIRMATION = auto()
    KIT_RELEASED                  = auto()
    COMPLETED                     = auto()
    ERROR                         = auto()


# 正常フローの順番
NORMAL_FLOW = [
    RobotState.IDLE,
    RobotState.REQUEST_RECEIVED,
    RobotState.KIT_SELECTED,
    RobotState.MOVING_TO_BEDSIDE,
    RobotState.VERIFYING_PATIENT,
    RobotState.DOCKING,
    RobotState.TRAY_LIFTING,
    RobotState.WAITING_FOR_NURSE_CONFIRMATION,
    RobotState.KIT_RELEASED,
    RobotState.COMPLETED,
]

STATE_MESSAGES = {
    RobotState.IDLE:                          "⬜ 待機中",
    RobotState.REQUEST_RECEIVED:              "🔔 リクエスト受信",
    RobotState.KIT_SELECTED:                  "📦 キット選択完了",
    RobotState.MOVING_TO_BEDSIDE:             "🤖 ベッドサイドへ移動中",
    RobotState.VERIFYING_PATIENT:             "🔍 患者ID照合中",
    RobotState.DOCKING:                       "🔗 ドッキング中",
    RobotState.TRAY_LIFTING:                  "⬆️  トレイ上昇中",
    RobotState.WAITING_FOR_NURSE_CONFIRMATION:"⏳ 看護師確認待ち",
    RobotState.KIT_RELEASED:                  "✅ キット開放済み",
    RobotState.COMPLETED:                     "🎉 タスク完了",
    RobotState.ERROR:                         "🚨 エラー発生",
}



# 文字列キーでアクセスできるバージョン（UI用）
STATE_LABELS = {
    "IDLE":                           "待機中",
    "REQUEST_RECEIVED":               "リクエスト受信",
    "KIT_SELECTED":                   "キット選択完了",
    "MOVING_TO_BEDSIDE":              "移動中",
    "VERIFYING_PATIENT":              "ID照合中",
    "DOCKING":                        "ドッキング中",
    "TRAY_LIFTING":                   "トレイ上昇中",
    "WAITING_FOR_NURSE_CONFIRMATION": "看護師確認待ち",
    "KIT_RELEASED":                   "キット開放",
    "COMPLETED":                      "完了",
    "ERROR":                          "エラー",
}
class RobotStateMachine:
    def __init__(self):
        self.state = RobotState.IDLE
        self.log: list[dict] = []
        self._log_event("初期化完了")

    def _log_event(self, message: str):
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "state": self.state.name,
            "message": message,
        }
        self.log.append(entry)
        print(f"[{entry['timestamp']}] {STATE_MESSAGES[self.state]}  — {message}")

    def transition(self, next_state: RobotState, reason: str = "") -> bool:
        """指定した状態へ遷移する。失敗した場合はERRORへ移行。"""
        allowed = self._allowed_transitions()
        if next_state not in allowed:
            print(f"⚠️  遷移不可: {self.state.name} → {next_state.name}")
            self.state = RobotState.ERROR
            self._log_event(f"不正な遷移: {next_state.name}")
            return False

        self.state = next_state
        self._log_event(reason if reason else next_state.name)
        return True

    def _allowed_transitions(self) -> list[RobotState]:
        """現在の状態から遷移できる状態の一覧"""
        if self.state == RobotState.ERROR:
            return [RobotState.IDLE]  # エラーからはリセットのみ

        if self.state in NORMAL_FLOW:
            idx = NORMAL_FLOW.index(self.state)
            next_states = []
            if idx + 1 < len(NORMAL_FLOW):
                next_states.append(NORMAL_FLOW[idx + 1])
            next_states.append(RobotState.ERROR)  # どこからでもERRORへは遷移可能
            return next_states

        return [RobotState.ERROR]

    def emergency_stop(self):
        self.state = RobotState.ERROR
        self._log_event("🛑 緊急停止")

    def reset(self):
        self.state = RobotState.IDLE
        self._log_event("リセット完了")

    def print_log(self):
        print("\n=== 動作ログ ===")
        for entry in self.log:
            print(f"  {entry['timestamp']} | {entry['state']:40s} | {entry['message']}")


# ── デモ実行 ───────────────────────────────────────────
if __name__ == "__main__":
    print("=== ロボット状態遷移デモ ===\n")

    robot = RobotStateMachine()
    time.sleep(0.1)

    steps = [
        (RobotState.REQUEST_RECEIVED,               "患者Aからトイレリクエスト受信"),
        (RobotState.KIT_SELECTED,                   "KIT_TOILETING_A を選択"),
        (RobotState.MOVING_TO_BEDSIDE,              "203号室ベッドサイドへ移動開始"),
        (RobotState.VERIFYING_PATIENT,              "QRコード読み取り・照合開始"),
        (RobotState.DOCKING,                        "照合OK → ドッキング開始"),
        (RobotState.TRAY_LIFTING,                   "トレイを高さ90cmに上昇"),
        (RobotState.WAITING_FOR_NURSE_CONFIRMATION, "看護師の確認を待機"),
        (RobotState.KIT_RELEASED,                   "看護師が確認ボタンを押した"),
        (RobotState.COMPLETED,                      "タスク完了"),
    ]

    for next_state, reason in steps:
        time.sleep(0.3)
        robot.transition(next_state, reason)

    robot.print_log()
