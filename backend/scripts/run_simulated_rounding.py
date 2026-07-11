"""Drive a full rounding session through the real backend API (PR25),
same spirit as `backend/scripts/run_simulated_delivery.py`: every call
goes through the real HTTP surface (`/rounding/*`, `/escalations/*`) a
real robot or the nurse dashboard would use, so no safety gate is
bypassed by taking an in-process shortcut.

Real person detection is out of scope (per the proposal doc: "実際の人物
検出...は不要です") -- `--detect-patient` is still a plain API call, not a
camera-driven trigger. Speech recognition is real as of PR29: pass
`--audio-file <path.wav>` to have this script transcribe an actual WAV
file offline (`perception/speech_recognizer.py`, faster-whisper) instead
of using a scenario's canned `simulated_response` text -- see that
option's own docstring in `run_rounding()` below. Without `--audio-file`,
each `--scenario` remains a pseudo patient-response event (room,
patient_id, simulated_response, expected_need, expected_priority) fed
straight into `POST /rounding/{id}/classify-need`, standing in for real
voice/tablet input.

By default this script *stops* at WAITING_FOR_NURSE_ACK for any scenario
that raises an escalation, and waits for a human to acknowledge it via
the real nurse dashboard (or a manual curl) -- it does not press that
button itself. Pass --auto-ack only if you explicitly want the script to
do that for you; the flag itself is your conscious confirmation, not a
way to silently bypass the gate (it still needs a valid nurse token to
succeed, same as the dashboard does). Scenarios that classify as
INFORMATION_ONLY have no nurse gate to begin with -- there is nothing for
--auto-ack to bypass -- so those always run to COMPLETED regardless of
the flag.

Examples:
    python -m backend.scripts.run_simulated_rounding \\
        --scenario rounding_toileting_escalation --nurse-token $NURSE_TOKEN
    python -m backend.scripts.run_simulated_rounding \\
        --scenario rounding_toileting_escalation --nurse-token $NURSE_TOKEN --auto-ack
"""
from __future__ import annotations

import argparse
import os
import time

import httpx

DEFAULT_ROOM = "203"
DEFAULT_PATIENT_ID = "PATIENT_A_ROOM_203"

# Pseudo patient-response events, one per named scenario. Each stands in
# for what a real voice/tablet interaction would eventually produce (see
# module docstring) -- `expected_need` / `expected_priority` are asserted
# against what `need_classification_service.classify()` actually returns,
# so this script doubles as a smoke test of that rule set end-to-end
# through the real API, not just a demo.
SCENARIOS: dict[str, dict] = {
    "rounding_normal": {
        "room": DEFAULT_ROOM,
        "patient_id": DEFAULT_PATIENT_ID,
        "simulated_response": "大丈夫です、特にないです",
        "expected_need": "information_only",
        "expected_priority": "LOW",
    },
    "rounding_patient_detected": {
        "room": DEFAULT_ROOM,
        "patient_id": DEFAULT_PATIENT_ID,
        "simulated_response": "少し不安で眠れないんです",
        "expected_need": "anxiety",
        "expected_priority": "MEDIUM",
    },
    "rounding_toileting_escalation": {
        "room": DEFAULT_ROOM,
        "patient_id": DEFAULT_PATIENT_ID,
        "simulated_response": "トイレに行きたいです",
        "expected_need": "toileting",
        "expected_priority": "HIGH",
    },
    "rounding_water_request": {
        "room": "204",
        "patient_id": "PATIENT_B_ROOM_204",
        "simulated_response": "お水が飲みたいです",
        "expected_need": "water",
        "expected_priority": "MEDIUM",
    },
    "rounding_no_need": {
        "room": DEFAULT_ROOM,
        "patient_id": DEFAULT_PATIENT_ID,
        "simulated_response": "大丈夫です",
        "expected_need": "information_only",
        "expected_priority": "LOW",
    },
    "rounding_urgent_pain": {
        "room": DEFAULT_ROOM,
        "patient_id": DEFAULT_PATIENT_ID,
        "simulated_response": "胸が痛いです、苦しいです",
        "expected_need": "pain",
        "expected_priority": "URGENT",
    },
    "rounding_fall_risk": {
        "room": DEFAULT_ROOM,
        "patient_id": DEFAULT_PATIENT_ID,
        "simulated_response": "ふらふらして、一人で立ち上がってしまいました",
        "expected_need": "fall_risk",
        "expected_priority": "URGENT",
    },
}

DEFAULT_SCENARIO = "rounding_toileting_escalation"


class RoundingScriptError(RuntimeError):
    pass


def _step(label: str) -> None:
    print(f"\n=== {label} ===")


def _request(client: httpx.Client, method: str, url: str, **kwargs) -> dict:
    try:
        response = client.request(method, url, **kwargs)
    except httpx.RequestError as exc:
        raise RoundingScriptError(f"Request to {url} failed: {exc}") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RoundingScriptError(f"{method} {url} -> {response.status_code}: {detail}")
    return response.json()


def run_rounding(
    client: httpx.Client,
    scenario: str = DEFAULT_SCENARIO,
    nurse_token: str = "",
    step_delay: float = 1.0,
    auto_ack: bool = False,
    ack_poll_seconds: float = 2.0,
    ack_timeout_seconds: float = 120.0,
    audio_file: "str | None" = None,
) -> dict:
    """Runs one simulated rounding session through the real API; returns
    the final `GET /rounding/{id}` view. Raises TimeoutError if the
    session escalates and nurse acknowledgement never arrives
    (auto_ack=False) within ack_timeout_seconds.

    `audio_file` (PR29): if given, the scenario's canned
    `simulated_response` text is replaced by the real transcription of
    that WAV file (via `perception.speech_recognizer.SpeechRecognizer`,
    offline/local -- see that module's docstring for why). `room` /
    `patient_id` still come from the scenario, and `input_mode` becomes
    "voice" instead of "simulated" -- but `expected_need`/
    `expected_priority` are NOT asserted in this mode, since a real
    speech-to-text transcription of the chosen phrase has no accuracy
    guarantee against the scenario's canned expectation. Whatever
    `need_classification_service` actually classifies the transcribed
    text as is printed and used as-is."""
    if scenario not in SCENARIOS:
        raise RoundingScriptError(
            f"Unknown scenario: {scenario!r}. Known scenarios: {sorted(SCENARIOS)}"
        )
    event = SCENARIOS[scenario]
    nurse_headers = {"x-nurse-token": nurse_token}

    if audio_file:
        from perception.speech_recognizer import SpeechRecognizer
        from perception.speech_source import WavFileSpeechSource

        _step("TRANSCRIBING AUDIO (offline, faster-whisper)")
        source = WavFileSpeechSource(audio_file)
        patient_response = SpeechRecognizer().transcribe_file(source.get_path())
        print(f"heard: {patient_response!r}")
        input_mode = "voice"
    else:
        patient_response = event["simulated_response"]
        input_mode = "simulated"

    _step("ROUNDING (robot begins rounding the ward)")
    started = _request(client, "POST", "/rounding/start", json={"room": event["room"]})
    session_id = started["rounding_session_id"]
    print(f"rounding_session_id={session_id} room={event['room']}")
    time.sleep(step_delay)

    _step("PATIENT_DETECTED")
    _request(
        client,
        "POST",
        f"/rounding/{session_id}/detect-patient",
        json={"patient_id": event["patient_id"]},
    )
    print(f"patient_id={event['patient_id']}")

    _step("APPROACHING_BEDSIDE -> INTERACTION_STARTED")
    interaction = _request(client, "POST", f"/rounding/{session_id}/start-interaction")
    print(f"prompt: {interaction['prompt']}")
    time.sleep(step_delay)

    _step("NEED_CLASSIFIED")
    classification = _request(
        client,
        "POST",
        f"/rounding/{session_id}/classify-need",
        json={
            "patient_response": patient_response,
            "input_mode": input_mode,
        },
    )
    print(
        f"detected_need={classification['detected_need']} "
        f"escalation_level={classification['escalation_level']} "
        f"route={classification['route']}"
    )
    if audio_file:
        print(
            "(--audio-file was used: expected_need/expected_priority are not "
            "asserted against a real transcription -- the classification "
            "above reflects whatever need_classification_service made of "
            "the actual recognized text.)"
        )
    else:
        if classification["detected_need"] != event["expected_need"]:
            raise RoundingScriptError(
                f"Scenario {scenario!r} expected detected_need="
                f"{event['expected_need']!r} but got {classification['detected_need']!r} "
                "-- need_classification_service's rules may have changed."
            )
        if classification["escalation_level"] != event["expected_priority"]:
            raise RoundingScriptError(
                f"Scenario {scenario!r} expected escalation_level="
                f"{event['expected_priority']!r} but got "
                f"{classification['escalation_level']!r}."
            )

    if classification["route"] == "INFORMATION_ONLY":
        _step("INFORMATION_PROVIDED -> COMPLETED (no nurse gate to cross)")
        _request(client, "POST", f"/rounding/{session_id}/provide-information")
        time.sleep(step_delay)
        final_state = _request(client, "GET", f"/rounding/{session_id}")
        print(f"\nRounding complete. Final status: {final_state['status']}")
        return final_state

    _step("ESCALATING_TO_NURSE -> WAITING_FOR_NURSE_ACK")
    escalated = _request(
        client,
        "POST",
        f"/rounding/{session_id}/escalate",
        json={
            "summary": classification["summary"],
            "priority": classification["escalation_level"],
            "suggested_action": classification["suggested_action"],
            "route": classification["route"],
        },
    )
    escalation_id = escalated["escalation_id"]
    print(f"escalation_id={escalation_id} summary: {classification['summary']}")

    if auto_ack:
        print(
            "\n--auto-ack was passed: this script will acknowledge the "
            "escalation itself using the nurse token it was given. In a "
            "real deployment, only a human nurse would do this."
        )
        time.sleep(step_delay)
        _request(
            client,
            "POST",
            f"/escalations/{escalation_id}/ack",
            json={"acknowledged_by": "simulated_nurse"},
            headers=nurse_headers,
        )
    else:
        print(
            f"\nWaiting for nurse acknowledgement on escalation {escalation_id}.\n"
            "Open the nurse dashboard and acknowledge this escalation, or run:\n"
            f"  curl -X POST $BASE_URL/escalations/{escalation_id}/ack "
            '-H "x-nurse-token: $NURSE_TOKEN" -H "Content-Type: application/json" '
            '-d \'{"acknowledged_by": "nurse_demo"}\'\n'
        )
        waited = 0.0
        while waited < ack_timeout_seconds:
            state = _request(client, "GET", f"/rounding/{session_id}")
            if state["status"] != "WAITING_FOR_NURSE_ACK":
                break
            time.sleep(ack_poll_seconds)
            waited += ack_poll_seconds
        else:
            raise TimeoutError(
                f"No nurse acknowledgement received within {ack_timeout_seconds}s "
                f"for escalation {escalation_id}. Session {session_id} is left at "
                "WAITING_FOR_NURSE_ACK -- acknowledge it manually whenever you're "
                "ready."
            )

    final_state = _request(client, "GET", f"/rounding/{session_id}")
    print(f"\nRounding complete. Final status: {final_state['status']}")
    return final_state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=os.getenv("PRECARE_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--nurse-token", default=os.getenv("NURSE_TOKEN", ""))
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO, choices=sorted(SCENARIOS))
    parser.add_argument("--step-delay", type=float, default=1.0, help="Seconds to pause between steps")
    parser.add_argument(
        "--auto-ack",
        action="store_true",
        help="Acknowledge the escalation (if any) automatically instead of waiting for a human.",
    )
    parser.add_argument(
        "--audio-file",
        default=None,
        help=(
            "PR29: path to a WAV file to transcribe offline (faster-whisper) "
            "instead of using the scenario's canned simulated_response text. "
            "room/patient_id still come from --scenario; expected_need/"
            "expected_priority are not asserted in this mode."
        ),
    )
    args = parser.parse_args()

    if not args.nurse_token:
        raise SystemExit(
            "NURSE_TOKEN is required (set --nurse-token or the NURSE_TOKEN env "
            "var) -- only used if the scenario escalates and --auto-ack is passed, "
            "but required upfront so a long-running scenario doesn't fail late."
        )

    with httpx.Client(base_url=args.base_url, timeout=5.0) as client:
        try:
            run_rounding(
                client,
                scenario=args.scenario,
                nurse_token=args.nurse_token,
                step_delay=args.step_delay,
                auto_ack=args.auto_ack,
                audio_file=args.audio_file,
            )
        except (RoundingScriptError, TimeoutError) as exc:
            raise SystemExit(f"run_simulated_rounding failed: {exc}") from exc


if __name__ == "__main__":
    main()
