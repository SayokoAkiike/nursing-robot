"use client";

import { useEffect, useRef, useState } from "react";
import { DeviceFrame } from "@/components/device-frame";
import { LoginScreen, type LoginDeviceVm } from "@/components/login-screen";
import { BedsideScreen } from "@/components/bedside/bedside-screen";
import { RobotScreen } from "@/components/robot/robot-screen";
import { NurseScreen, type NurseSubTab } from "@/components/nurse/nurse-screen";
import type { EscalationVm } from "@/components/nurse/escalations-tab";
import type { PatientOverviewVm } from "@/components/nurse/patients-tab";
import type { HistoryBucketVm } from "@/components/nurse/robot-history-tab";
import type { VoiceTurnResult } from "@/hooks/use-voice-recorder";
import { runRoundingInteraction, roomNumberFor, type RoundingOutcome } from "@/lib/rounding-api";
import {
  HISTORY_BUCKET_DEFS,
  MOOD_LEVELS,
  NURSE_NAME,
  PATIENTS,
  PRIORITY_META,
  buildEscalation,
  buildHistoryRecordFromRun,
  classify,
  currentTimestamp,
  seedHistory,
  timeLabelFor,
} from "@/lib/mock-data";
import type {
  ChatMessage,
  ConversationEntry,
  DeviceType,
  Escalation,
  HistoryRecord,
  MoodId,
  QuickRequest,
} from "@/lib/types";

type LoginInputs = { facilityId: string; personalId: string };
const EMPTY_LOGIN_INPUTS: Record<DeviceType, LoginInputs> = {
  bedside: { facilityId: "", personalId: "" },
  robot: { facilityId: "", personalId: "" },
  nurse: { facilityId: "", personalId: "" },
};
const DEVICE_LABELS: Record<DeviceType, string> = {
  bedside: "患者ベッドサイドタブレット",
  robot: "みまもりロボット",
  nurse: "ナースステーションPC",
};

const INITIAL_ESCALATIONS: Escalation[] = [
  { id: "e1", patient: "田中さん", room: "203号室", request: "トイレに行きたいです", priority: "urgent", time: "14:12", status: "active", assignedNurse: null },
  { id: "e2", patient: "佐藤さん", room: "105号室", request: "お水が飲みたいです", priority: "normal", time: "13:50", status: "acknowledged", assignedNurse: "田中 明子 看護師" },
  { id: "e3", patient: "鈴木さん", room: "301号室", request: "少し話し相手が欲しいです", priority: "normal", time: "13:20", status: "resolved", assignedNurse: "加藤 健一 看護師" },
  { id: "e4", patient: "高橋さん", room: "110号室", request: "膝が痛みます", priority: "urgent", time: "12:45", status: "resolved", assignedNurse: "渡辺 真由美 看護師" },
];

function buildRoundingConversationEntries(
  patient: { name: string; room: string },
  outcome: RoundingOutcome,
  robotAudioText: string,
): ConversationEntry[] {
  const meta = PRIORITY_META[outcome.priority];
  return [
    { kind: "system", text: "ロボットが病室の巡回を開始しました" },
    { kind: "system", text: `${patient.name}（${patient.room}）を発見しました` },
    { kind: "robot", text: outcome.prompt },
    { kind: "patient", text: outcome.utterance, initial: patient.name.charAt(0) },
    {
      kind: "classification",
      category: outcome.needLabel,
      priority: outcome.priority,
      priorityLabel: meta.label,
      route: outcome.route,
    },
    { kind: "robot-audio", text: robotAudioText },
    {
      kind: "complete",
      text:
        outcome.workflow === "delivery"
          ? "配送ワークフローに接続しました"
          : outcome.workflow === "information"
            ? "看護師エスカレーションは不要と判断され、対応完了として記録しました"
            : "エスカレーションを作成しました",
    },
  ];
}

export function NurselinkApp() {
  const [activeDevice, setActiveDevice] = useState<DeviceType | null>(null);
  const [loginInputs, setLoginInputs] = useState(EMPTY_LOGIN_INPUTS);
  const [qrScanningDevice, setQrScanningDevice] = useState<DeviceType | null>(null);
  const [bedsideView, setBedsideView] = useState<"home" | "schedule">("home");

  const [selectedPatientId, setSelectedPatientId] = useState("p1");
  const [isRunning, setIsRunning] = useState(false);
  const [stepRevealCount, setStepRevealCount] = useState(0);
  const [entriesForRun, setEntriesForRun] = useState<ConversationEntry[]>([]);
  const [playingAudio, setPlayingAudio] = useState(false);
  const [voiceAudioUrl, setVoiceAudioUrl] = useState<string | null>(null);
  const [roundingError, setRoundingError] = useState<string | null>(null);

  const [nurseSubTab, setNurseSubTab] = useState<NurseSubTab>("patients");
  const [dashTab, setDashTab] = useState<"open" | "resolved">("open");
  const [recalledId, setRecalledId] = useState<string | null>(null);
  const [callingId, setCallingId] = useState<string | null>(null);
  const [dismissedIds, setDismissedIds] = useState<string[]>([]);
  const [nurseRobotPatientId, setNurseRobotPatientId] = useState("p1");
  const [nurseRobotSelectedRecordId, setNurseRobotSelectedRecordId] = useState<string | null>(null);
  const [conversationHistory, setConversationHistory] = useState<HistoryRecord[]>(() => seedHistory());
  const [escalations, setEscalations] = useState<Escalation[]>(INITIAL_ESCALATIONS);

  const [bedsidePatientId, setBedsidePatientId] = useState("p1");
  const [bedsideMood, setBedsideMood] = useState<MoodId>("neutral");
  const [bedsideFlashText, setBedsideFlashText] = useState("");
  const [bedsideChat, setBedsideChat] = useState<ChatMessage[]>([
    { from: "nurse", text: "田中さん、おはようございます！体調はいかがですか？" },
  ]);
  const [bedsideChatInput, setBedsideChatInput] = useState("");
  const [emergencySent, setEmergencySent] = useState(false);
  const [now, setNow] = useState(() => currentTimestamp());

  const patrolTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const audioElRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      if (patrolTimer.current) clearInterval(patrolTimer.current);
      if (flashTimer.current) clearTimeout(flashTimer.current);
    };
  }, []);

  const refreshNow = () => setNow(currentTimestamp());

  const patients = PATIENTS.map((p) => ({ id: p.id, label: `${p.name}（${p.room}）` }));

  // ---- Login screen ----
  const loginDevices: LoginDeviceVm[] = (["bedside", "robot", "nurse"] as DeviceType[]).map((d) => ({
    id: d,
    label: DEVICE_LABELS[d],
    facilityId: loginInputs[d].facilityId,
    personalId: loginInputs[d].personalId,
    onFacilityIdChange: (value) =>
      setLoginInputs((s) => ({ ...s, [d]: { ...s[d], facilityId: value } })),
    onPersonalIdChange: (value) =>
      setLoginInputs((s) => ({ ...s, [d]: { ...s[d], personalId: value } })),
    onLogin: () => {
      setActiveDevice(d);
      setBedsideView("home");
    },
    onScanQr: () => {
      setQrScanningDevice(d);
      setTimeout(() => {
        setActiveDevice(d);
        setQrScanningDevice(null);
        setBedsideView("home");
      }, 1100);
    },
    qrScanning: qrScanningDevice === d,
  }));

  const goToDeviceSelect = () => {
    setActiveDevice(null);
    setLoginInputs(EMPTY_LOGIN_INPUTS);
  };

  // ---- Escalations shared logic ----
  const activeCount = escalations.filter((e) => e.status !== "resolved").length;
  const resolvedCount = escalations.filter((e) => e.status === "resolved").length;

  const addEscalationFromBedside = (
    patient: { name: string; room: string },
    requestText: string,
    priorityOverride: Escalation["priority"] | null,
  ) => {
    const result = classify(requestText, null);
    const priority = priorityOverride ?? result.priority;
    const newEsc = buildEscalation(patient, requestText, priority);
    setEscalations((s) => [newEsc, ...s]);
  };

  const acknowledgeEscalation = (id: string) => {
    setEscalations((s) =>
      s.map((e) => (e.id === id ? { ...e, status: "acknowledged", assignedNurse: NURSE_NAME } : e)),
    );
  };
  const resolveEscalation = (id: string) => {
    setEscalations((s) => s.map((e) => (e.id === id ? { ...e, status: "resolved" } : e)));
  };
  const dismissFromPatientList = (id: string) => {
    setDismissedIds((s) => [...s, id]);
  };
  const recallEscalation = (id: string) => {
    setRecalledId(id);
    setTimeout(() => setRecalledId((cur) => (cur === id ? null : cur)), 1600);
  };
  const callPatientAction = (id: string) => {
    setCallingId(id);
    setTimeout(() => setCallingId((cur) => (cur === id ? null : cur)), 1600);
  };

  const playAudio = () => {
    const audioEl = audioElRef.current;
    if (!audioEl || !audioEl.src) return;
    if (playingAudio) {
      audioEl.pause();
      setPlayingAudio(false);
    } else {
      void audioEl.play();
      setPlayingAudio(true);
    }
  };

  // ---- Robot patrol: tap "話しかける" to record a real mic utterance, send
  // it to the selected voice engine (backend/services/voice_backends/), then
  // run the transcript through the real backend/services/rounding_service.py
  // state machine (start -> detect-patient -> start-interaction ->
  // classify-need -> escalate/require-delivery/provide-information) via
  // /api/rounding -- the same sequence demo/pages/3_🚶_巡回・要望分類デモ.py
  // drives -- then reveal the result step by step in the same request-history
  // flow the old canned demo scenario used. ----
  const runVoiceTurn = async (voiceResult: VoiceTurnResult) => {
    if (isRunning) return;
    const patient = PATIENTS.find((p) => p.id === selectedPatientId) ?? PATIENTS[0];
    const utterance = voiceResult.transcript || "（発話を認識できませんでした）";

    setIsRunning(true);
    setRoundingError(null);
    setStepRevealCount(0);
    setEntriesForRun([]);
    setPlayingAudio(false);
    setVoiceAudioUrl(voiceResult.audioUrl);

    let outcome: RoundingOutcome;
    try {
      outcome = await runRoundingInteraction({
        room: roomNumberFor(patient.room),
        patientId: patient.id,
        patientResponse: utterance,
        inputMode: "voice",
      });
    } catch (err) {
      setIsRunning(false);
      setRoundingError(err instanceof Error ? err.message : "要望分類の実行に失敗しました。");
      return;
    }

    const entries = buildRoundingConversationEntries(
      patient,
      outcome,
      voiceResult.responseText || outcome.ackText,
    );
    setEntriesForRun(entries);

    let count = 0;
    patrolTimer.current = setInterval(() => {
      count += 1;
      setStepRevealCount(count);
      if (count >= entries.length) {
        if (patrolTimer.current) clearInterval(patrolTimer.current);
        setIsRunning(false);
        const newEsc = buildEscalation(patient, utterance, outcome.priority);
        const newRecord = buildHistoryRecordFromRun(patient.id, utterance, outcome.priority, entries);
        setEscalations((s) => [newEsc, ...s]);
        setConversationHistory((s) => [newRecord, ...s]);
        refreshNow();
      }
    }, 700);
  };

  const revealedEntries = entriesForRun.slice(0, stepRevealCount);
  const lastRobotEntry = [...revealedEntries].reverse().find((e) => e.kind === "robot" || e.kind === "robot-audio") ?? null;
  const lastPatientEntry = [...revealedEntries].reverse().find((e) => e.kind === "patient") ?? null;
  const lastEntry = revealedEntries.length ? revealedEntries[revealedEntries.length - 1] : null;
  const hasCaption = !!lastRobotEntry || !!lastPatientEntry;
  const robotCaptionActive = !!lastEntry && (lastEntry.kind === "robot" || lastEntry.kind === "robot-audio");
  const patientCaptionActive = !!lastEntry && lastEntry.kind === "patient";
  const selectedPatient = PATIENTS.find((p) => p.id === selectedPatientId) ?? PATIENTS[0];

  // ---- Bedside ----
  const bedsidePatient = PATIENTS.find((p) => p.id === bedsidePatientId) ?? PATIENTS[0];

  const flashMessage = (text: string) => {
    setBedsideFlashText(text);
    if (flashTimer.current) clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setBedsideFlashText(""), 2600);
  };

  const sendBedsideQuickRequest = (q: QuickRequest) => {
    addEscalationFromBedside(bedsidePatient, q.phrase, null);
    flashMessage(`「${q.label}」を送信しました。ナースに通知しました。`);
  };

  const sendBedsideVoiceRequest = (voiceResult: VoiceTurnResult) => {
    const utterance = voiceResult.transcript || "（発話を認識できませんでした）";
    addEscalationFromBedside(bedsidePatient, utterance, null);
    flashMessage(`音声リクエスト「${utterance}」を送信しました。ナースに通知しました。`);
  };

  const reportBedsidePain = () => {
    const mood = MOOD_LEVELS.find((m) => m.id === bedsideMood)!;
    const priority = mood.score >= 7 ? "urgent" : "normal";
    addEscalationFromBedside(bedsidePatient, `いつもと比べて「${mood.label}」と報告`, priority);
    flashMessage(`今の状態（${mood.label}）を報告しました。`);
  };

  const sendBedsideChat = () => {
    const text = bedsideChatInput.trim();
    if (!text) return;
    setBedsideChat((s) => [...s, { from: "patient", text }]);
    setBedsideChatInput("");
    setTimeout(() => {
      setBedsideChat((s) => [...s, { from: "nurse", text: "承知しました。担当スタッフにお伝えしますね。" }]);
    }, 900);
  };

  const triggerEmergency = () => {
    if (emergencySent) return;
    addEscalationFromBedside(bedsidePatient, "緊急呼び出しボタンが押されました", "urgent");
    setEmergencySent(true);
    setTimeout(() => setEmergencySent(false), 4000);
  };

  // ---- Nurse: patients tab ----
  const patientOverviews: PatientOverviewVm[] = PATIENTS.map((p) => {
    const latest = escalations.find((e) => e.patient === p.name && !dismissedIds.includes(e.id)) ?? null;
    return {
      id: p.id,
      name: p.name,
      room: p.room,
      initial: p.name.charAt(0),
      hasRequest: !!latest,
      priority: latest ? latest.priority : null,
      requestText: latest ? `「${latest.request}」` : "リクエスト・メッセージはありません",
      timeLabel: latest ? (latest.status === "resolved" ? `対応済み・${latest.time}` : latest.time) : "—",
      canResolve: !!latest && latest.status !== "resolved",
      canDismiss: !!latest && latest.status === "resolved",
      onResolve: latest ? () => resolveEscalation(latest.id) : () => {},
      onDismiss: latest ? () => dismissFromPatientList(latest.id) : () => {},
    };
  });

  // ---- Nurse: escalations tab ----
  const visibleEscalations: EscalationVm[] = escalations
    .filter((e) => (dashTab === "resolved" ? e.status === "resolved" : e.status !== "resolved"))
    .map((e) => ({
      id: e.id,
      patient: e.patient,
      room: e.room,
      request: e.request,
      time: e.time,
      initial: e.patient.charAt(0),
      priority: e.priority,
      status: e.status,
      assignedNurse: e.assignedNurse,
      recallLabel: recalledId === e.id ? "呼び出しました ✓" : "再度呼び出し",
      callLabel: callingId === e.id ? "発信中…" : "患者へ発信",
      onAcknowledge: () => acknowledgeEscalation(e.id),
      onResolve: () => resolveEscalation(e.id),
      onRecall: () => recallEscalation(e.id),
      onCallPatient: () => callPatientAction(e.id),
    }));

  // ---- Nurse: robot history tab ----
  const historyRecords = conversationHistory
    .filter((r) => r.patientId === nurseRobotPatientId)
    .slice()
    .sort((a, b) => b.timestamp - a.timestamp);

  const bucketLists: HistoryRecord[][] = HISTORY_BUCKET_DEFS.map(() => []);
  historyRecords.forEach((r) => {
    const hoursAgo = (now - r.timestamp) / 3600000;
    const idx = HISTORY_BUCKET_DEFS.findIndex((bd) => hoursAgo <= bd.max);
    bucketLists[idx === -1 ? bucketLists.length - 1 : idx].push(r);
  });

  const historyBuckets: HistoryBucketVm[] = HISTORY_BUCKET_DEFS.map((bd, i) => ({
    label: bd.label,
    records: bucketLists[i].map((r) => ({
      id: r.id,
      summary: r.summary,
      priority: r.priority,
      timeLabel: timeLabelFor((now - r.timestamp) / 3600000),
      onSelect: () => {
        setNurseRobotSelectedRecordId(r.id);
        refreshNow();
      },
    })),
  })).filter((b) => b.records.length > 0);

  const selectedRecord = nurseRobotSelectedRecordId
    ? conversationHistory.find((r) => r.id === nurseRobotSelectedRecordId) ?? null
    : null;

  return (
    <div className="min-h-screen w-full box-border" style={{ background: "oklch(0.985 0.002 260)", color: "oklch(0.18 0.004 260)", padding: 32 }}>
      <header className="mx-auto mb-6 flex items-baseline gap-3" style={{ maxWidth: 1600 }}>
        <div className="text-[15px] font-bold tracking-[0.01em]">Nurselink</div>
        <div className="text-[12.5px]" style={{ color: "oklch(0.55 0.01 260)" }}>
          デモ環境 · ロボット巡回はバックエンドAPIに接続
        </div>
      </header>

      {!activeDevice && <LoginScreen devices={loginDevices} />}

      {activeDevice === "bedside" && (
        <DeviceFrame title="患者ベッドサイドタブレット" maxWidth={640} onSwitchDevice={goToDeviceSelect}>
          <BedsideScreen
            view={bedsideView}
            patients={patients}
            bedsidePatientId={bedsidePatientId}
            bedsidePatientLabel={bedsidePatient.name}
            onSelectPatient={setBedsidePatientId}
            onGoToSchedule={() => setBedsideView("schedule")}
            onBackFromSchedule={() => setBedsideView("home")}
            onSendQuickRequest={sendBedsideQuickRequest}
            flashText={bedsideFlashText}
            moodId={bedsideMood}
            onSelectMood={setBedsideMood}
            onReportMood={reportBedsidePain}
            chat={bedsideChat}
            chatInput={bedsideChatInput}
            onChatInputChange={setBedsideChatInput}
            onSendChat={sendBedsideChat}
            emergencySent={emergencySent}
            onTriggerEmergency={triggerEmergency}
            onVoiceRequest={sendBedsideVoiceRequest}
          />
        </DeviceFrame>
      )}

      {activeDevice === "robot" && (
        <DeviceFrame title="みまもりロボット · ロボット搭載ディスプレイ" maxWidth={1180} onSwitchDevice={goToDeviceSelect}>
          <RobotScreen
            patients={patients}
            selectedPatientId={selectedPatientId}
            onSelectPatient={setSelectedPatientId}
            isRunning={isRunning}
            patientBannerLabel={`${selectedPatient.name}（${selectedPatient.room}）を見守り中`}
            patientBannerName={selectedPatient.name}
            patientInitial={selectedPatient.name.charAt(0)}
            stepRevealCount={stepRevealCount}
            revealedEntries={revealedEntries}
            hasCaption={hasCaption}
            robotCaptionText={lastRobotEntry && "text" in lastRobotEntry ? lastRobotEntry.text : ""}
            patientCaptionText={lastPatientEntry && "text" in lastPatientEntry ? lastPatientEntry.text : ""}
            robotCaptionActive={robotCaptionActive}
            patientCaptionActive={patientCaptionActive}
            playingAudio={playingAudio}
            onPlayAudio={playAudio}
            onVoiceTurnResult={runVoiceTurn}
            roundingError={roundingError}
          />
          <audio
            ref={audioElRef}
            src={voiceAudioUrl ?? undefined}
            onEnded={() => setPlayingAudio(false)}
            className="hidden"
          />
        </DeviceFrame>
      )}

      {activeDevice === "nurse" && (
        <DeviceFrame
          title="ナースステーションPC"
          maxWidth={1180}
          onSwitchDevice={goToDeviceSelect}
          rightBadge={
            activeCount > 0 ? (
              <span
                className="ml-auto rounded-[10px] px-[7px] py-px text-center text-[11px] font-semibold text-white"
                style={{ background: "oklch(0.58 0.19 25)", minWidth: 18 }}
              >
                {activeCount}
              </span>
            ) : undefined
          }
        >
          <NurseScreen
            subTab={nurseSubTab}
            onSetSubTab={(tab) => {
              setNurseSubTab(tab);
              refreshNow();
            }}
            patientOverviews={patientOverviews}
            dashTab={dashTab}
            onSetDashTab={setDashTab}
            activeCount={activeCount}
            resolvedCount={resolvedCount}
            visibleEscalations={visibleEscalations}
            patients={patients}
            nurseRobotPatientId={nurseRobotPatientId}
            onSelectNurseRobotPatient={(id) => {
              setNurseRobotPatientId(id);
              setNurseRobotSelectedRecordId(null);
              refreshNow();
            }}
            historyMode={nurseRobotSelectedRecordId ? "detail" : "list"}
            hasNoHistory={historyRecords.length === 0}
            historyBuckets={historyBuckets}
            selectedRecordTimeLabel={
              selectedRecord ? timeLabelFor((now - selectedRecord.timestamp) / 3600000) : ""
            }
            selectedRecordEntries={selectedRecord ? selectedRecord.entries : []}
            onCloseHistoryDetail={() => {
              setNurseRobotSelectedRecordId(null);
              refreshNow();
            }}
          />
        </DeviceFrame>
      )}
    </div>
  );
}
