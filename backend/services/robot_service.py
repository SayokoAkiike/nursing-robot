"""Robot workflow finite-state machine.
 
This is the single source of truth for "what state transitions are legal".
 
Previously this logic existed in two places that could drift apart:
  - `robot_control/state_machine.py`'s `RobotStateMachine` class, which
    derived legal transitions from the *position* of a state in
    `NORMAL_FLOW`. That derivation was actually looser than intended: because
    VERIFYING_PATIENT is immediately followed by DOCKING in `NORMAL_FLOW`,
    the class would happily accept a *generic* transition straight from
    VERIFYING_PATIENT to DOCKING -- silently bypassing the QR verification
    step that `verification_service.verify_ids()` is supposed to enforce.
  - `robot_control/service.py`'s `ALLOWED_TRANSITIONS` dict, which is what
    actually backed the running API and deliberately has no
    "VERIFYING_PATIENT" key for exactly that reason.
 
  Only the class was covered by `tests/test_state_machine.py`; the dict was
  covered by `tests/test_api.py` / `tests/test_service.py`. Nothing would
  have caught the two rulesets disagreeing.
 
`ALLOWED_TRANSITIONS` below is now the only ruleset. `workflow_service`
(generic transitions) and `verification_service` (the one legal way to reach
DOCKING) both build on it, and `RobotStateMachine` -- kept only for the CLI
demo at the bottom of this file -- is a thin wrapper around the same
functions instead of a second implementation.
"""
 
from datetime import datetime
from enum import Enum
 
 
class RobotState(str, Enum):
    IDLE = "IDLE"
    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    KIT_SELECTED = "KIT_SELECTED"
    MOVING_TO_BEDSIDE = "MOVING_TO_BEDSIDE"
    VERIFYING_PATIENT = "VERIFYING_PATIENT"
    DOCKING = "DOCKING"
    TRAY_LIFTING = "TRAY_LIFTING"
    WAITING_FOR_NURSE_CONFIRMATION = "WAITING_FOR_NURSE_CONFIRMATION"
    KIT_RELEASED = "KIT_RELEASED"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
 
 
# Order shown to humans (nurse dashboard progress bar / CLI demo log).
DISPLAY_FLOW = [
    "REQUEST_RECEIVED",
    "KIT_SELECTED",
    "MOVING_TO_BEDSIDE",
    "VERIFYING_PATIENT",
    "DOCKING",
    "TRAY_LIFTING",
    "WAITING_FOR_NURSE_CONFIRMATION",
    "KIT_RELEASED",
    "COMPLETED",
]
 
STATE_LABELS = {
    "IDLE": "待機中",
    "REQUEST_RECEIVED": "リクエスト受信",
    "KIT_SELECTED": "キット選択完了",
    "MOVING_TO_BEDSIDE": "移動中",
    "VERIFYING_PATIENT": "ID照合中",
    "DOCKING": "ドッキング中",
    "TRAY_LIFTING": "トレイ上昇中",
    "WAITING_FOR_NURSE_CONFIRMATION": "看護師確認待ち",
    "KIT_RELEASED": "キット開放",
    "COMPLETED": "完了",
    "ERROR": "エラー",
}
 
STATE_MESSAGES = {
    "IDLE": "⬜ 待機中",
    "REQUEST_RECEIVED": "🔔 リクエスト受信",
    "KIT_SELECTED": "📦 キット選択完了",
    "MOVING_TO_BEDSIDE": "🤖 ベッドサイドへ移動中",
    "VERIFYING_PATIENT": "🔍 患者ID照合中",
    "DOCKING": "🔗 ドッキング中",
    "TRAY_LIFTING": "⬆️  トレイ上昇中",
    "WAITING_FOR_NURSE_CONFIRMATION": "⏳ 看護師確認待ち",
    "KIT_RELEASED": "✅ キット開放済み",
    "COMPLETED": "🎉 タスク完了",
    "ERROR": "🚨 エラー発生",
}
 
# current -> next. Deliberately excludes:
#   - "IDLE" (genesis only happens via workflow_service.create_request)
#   - "VERIFYING_PATIENT" (the only legal way out is verification_service's
#     verify_ids(); see verify_transition() below)
ALLOWED_TRANSITIONS = {
    "REQUEST_RECEIVED": "KIT_SELECTED",
    "KIT_SELECTED": "MOVING_TO_BEDSIDE",
    "MOVING_TO_BEDSIDE": "VERIFYING_PATIENT",
    "DOCKING": "TRAY_LIFTING",
    "TRAY_LIFTING": "WAITING_FOR_NURSE_CONFIRMATION",
    "WAITING_FOR_NURSE_CONFIRMATION": "KIT_RELEASED",
    "KIT_RELEASED": "COMPLETED",
}
 
 
def allowed_next_state(current: str) -> str | None:
    return ALLOWED_TRANSITIONS.get(current)
 
 
def is_valid_transition(current: str, next_state: str) -> bool:
    return allowed_next_state(current) == next_state
 
 
def verify_transition(current: str) -> str | None:
    """The one legal transition target reachable only via QR verification."""
    if current == RobotState.VERIFYING_PATIENT.value:
        return RobotState.DOCKING.value
    return None
 
 
# ---------------------------------------------------------------------------
# CLI demo only (`python -m backend.services.robot_service`). Not used by the
# API; kept for local exploration of the workflow without a server running.
# ---------------------------------------------------------------------------
class RobotStateMachine:
    def __init__(self):
        self.state = RobotState.IDLE.value
        self.log: list[dict] = []
        self._log_event("初期化完了")
 
    def _log_event(self, message: str):
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "state": self.state,
            "message": message,
        }
        self.log.append(entry)
        print(f"[{entry['timestamp']}] {STATE_MESSAGES[self.state]}  — {message}")
 
    def receive_request(self, reason: str = "") -> None:
        """Mirrors workflow_service.create_request(): only legal from IDLE."""
        self.state = RobotState.REQUEST_RECEIVED.value
        self._log_event(reason or "リクエスト受信")
 
    def transition(self, next_state: str, reason: str = "") -> bool:
        if is_valid_transition(self.state, next_state):
            self.state = next_state
            self._log_event(reason or next_state)
            return True
        print(f"⚠️  遷移不可: {self.state} → {next_state}")
        self.state = RobotState.ERROR.value
        self._log_event(f"不正な遷移: {next_state}")
        return False
 
    def simulate_verification(self, reason: str = "QRコード読み取り・照合OK") -> bool:
        """Mirrors verification_service.verify_ids(): the only path from
        VERIFYING_PATIENT to DOCKING."""
        target = verify_transition(self.state)
        if target is None:
            self.state = RobotState.ERROR.value
            self._log_event("照合できない状態からの照合試行")
            return False
        self.state = target
        self._log_event(reason)
        return True
 
    def emergency_stop(self):
        self.state = RobotState.ERROR.value
        self._log_event("🛑 緊急停止")
 
    def reset(self):
        self.state = RobotState.IDLE.value
        self._log_event("リセット完了")
 
    def print_log(self):
        print("\n=== 動作ログ ===")
        for entry in self.log:
            print(f"  {entry['timestamp']} | {entry['state']:40s} | {entry['message']}")
 
 
if __name__ == "__main__":
    print("=== ロボット状態遷移デモ ===\n")
 
    robot = RobotStateMachine()
    robot.receive_request("患者Aからトイレリクエスト受信")
    robot.transition(RobotState.KIT_SELECTED.value, "KIT_TOILETING_A を選択")
    robot.transition(RobotState.MOVING_TO_BEDSIDE.value, "203号室ベッドサイドへ移動開始")
    robot.transition(RobotState.VERIFYING_PATIENT.value, "QRコード読み取り・照合開始")
    robot.simulate_verification("照合OK → ドッキング開始")
    robot.transition(RobotState.TRAY_LIFTING.value, "トレイを高さ90cmに上昇")
    robot.transition(RobotState.WAITING_FOR_NURSE_CONFIRMATION.value, "看護師の確認を待機")
    robot.transition(RobotState.KIT_RELEASED.value, "看護師が確認ボタンを押した")
    robot.transition(RobotState.COMPLETED.value, "タスク完了")
 
    robot.print_log()
 
