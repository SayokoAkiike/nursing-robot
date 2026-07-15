import type {
  ClassificationResult,
  ConversationEntry,
  Escalation,
  HistoryRecord,
  MoodLevel,
  Patient,
  Priority,
  QuickRequest,
  ScheduleItem,
} from "./types";

export const PATIENTS: Patient[] = [
  { id: "p1", name: "田中さん", room: "203号室" },
  { id: "p2", name: "佐藤さん", room: "105号室" },
  { id: "p3", name: "鈴木さん", room: "301号室" },
  { id: "p4", name: "高橋さん", room: "110号室" },
];

export const SAMPLE_PHRASES = [
  "トイレに行きたいです",
  "お腹が痛いです",
  "喉が渇きました、お水がほしいです",
  "特に用事はありません、少し話し相手が欲しいだけです",
];

export const QUICK_REQUESTS: QuickRequest[] = [
  { label: "トイレ", phrase: "トイレに行きたいです", kind: "toilet" },
  { label: "点滴", phrase: "点滴の様子を見てほしいです", kind: "drip" },
  { label: "体位交換", phrase: "体位を変えてもらいたいです", kind: "reposition" },
  { label: "吸引", phrase: "痰の吸引をお願いしたいです", kind: "suction" },
  { label: "お薬", phrase: "お薬の時間について聞きたいです", kind: "medicine" },
  { label: "お水", phrase: "喉が渇きました、お水がほしいです", kind: "water" },
];

export const MOOD_LEVELS: MoodLevel[] = [
  { id: "worst", label: "とても辛い", score: 9, hue: 25 },
  { id: "bad", label: "つらい", score: 7, hue: 60 },
  { id: "neutral", label: "いつも通り", score: 4, hue: 250 },
  { id: "good", label: "良い", score: 2, hue: 190 },
  { id: "great", label: "とても良い", score: 0, hue: 150 },
];

export const NURSE_NAME = "佐藤 花子 看護師";

export const ROBOT_STAGE_DEFS = [
  { label: "リクエスト受信", threshold: 4 },
  { label: "キット配送", threshold: 5 },
  { label: "QR患者個別照合", threshold: 6 },
  { label: "看護師確認", threshold: 7 },
];

export const SCHEDULE_ITEMS: ScheduleItem[] = [
  { time: "08:00", task: "朝食", note: "常食を部屋にお届けしました", status: "done" },
  { time: "09:00", task: "朝の薬", note: "看護師が投与済み", status: "done" },
  { time: "10:00", task: "採血", note: "検査技師 鈴木が伺います", status: "upcoming" },
  { time: "12:00", task: "昼食", note: "低塩分メニュー", status: "upcoming" },
  { time: "14:00", task: "回診", note: "山田医師による回診", status: "upcoming" },
];

export const PRIORITY_META: Record<
  Priority,
  { label: string; badge: string; cardBorder: string }
> = {
  urgent: {
    label: "緊急",
    badge: "background:oklch(0.95 0.03 25); color:oklch(0.5 0.17 25);",
    cardBorder: "oklch(0.6 0.17 25)",
  },
  normal: {
    label: "通常",
    badge: "background:oklch(0.95 0.035 85); color:oklch(0.5 0.12 80);",
    cardBorder: "oklch(0.68 0.12 85)",
  },
};

export function classify(text: string, painScale: number | null): ClassificationResult {
  const t = text || "";
  let base: Omit<ClassificationResult, "vasScore">;

  if (t.includes("トイレ") || t.includes("排泄")) {
    base = {
      category: "排泄介助",
      priority: "urgent",
      route: "介護スタッフへ即時通知",
      response: "かしこまりました。すぐに介護スタッフにお伝えします。少々お待ちください。",
      workflow: "escalation",
    };
  } else if (t.includes("吸引") || t.includes("痰")) {
    base = {
      category: "吸引・処置",
      priority: "urgent",
      route: "看護師へエスカレーション",
      response: "承知しました。看護師がすぐに伺います。",
      workflow: "escalation",
    };
  } else if (t.includes("点滴")) {
    base = {
      category: "点滴確認",
      priority: "urgent",
      route: "看護師へエスカレーション",
      response: "かしこまりました。看護師が点滴の状態を確認しに伺います。",
      workflow: "escalation",
    };
  } else if (t.includes("体位")) {
    base = {
      category: "体位交換",
      priority: "normal",
      route: "介護スタッフへ通知",
      response: "承知しました。介護スタッフが体位交換のお手伝いに伺います。",
      workflow: "escalation",
    };
  } else if (t.includes("痛い") || t.includes("苦し") || t.includes("気分")) {
    base = {
      category: "体調不良",
      priority: "urgent",
      route: "看護師へエスカレーション",
      response:
        "承知しました。ただちに看護師へ連絡します。無理をせず楽な姿勢でお待ちください。",
      workflow: "escalation",
    };
  } else if (t.includes("水") || t.includes("お茶") || t.includes("渇")) {
    base = {
      category: "飲食物リクエスト",
      priority: "normal",
      route: "配膳ワークフローに接続",
      response: "かしこまりました。お飲み物をお届けする手配をいたします。",
      workflow: "delivery",
    };
  } else if (t.includes("薬")) {
    base = {
      category: "服薬案内",
      priority: "normal",
      route: "記録として保存",
      response: "お薬の時間になりましたら改めてお知らせいたします。",
      workflow: "escalation",
    };
  } else if (t.includes("つらさ") || t.includes("症状")) {
    base = {
      category: "症状報告",
      priority: "normal",
      route: "看護師へ共有",
      response: "症状の報告を受け取りました。",
      workflow: "escalation",
    };
  } else {
    base = {
      category: "その他・会話",
      priority: "normal",
      route: "記録として保存",
      response: "お話しいただきありがとうございます。またいつでもお声がけください。",
      workflow: "escalation",
    };
  }

  const vas = typeof painScale === "number" ? painScale : null;
  if (vas !== null && vas >= 7 && base.priority !== "urgent") {
    base = {
      ...base,
      priority: "urgent",
      route: base.route + "（VASスコアにより優先度を自動引き上げ）",
      autoEscalated: true,
    };
  }

  return { ...base, vasScore: vas };
}

function buildHistoryEntries(
  patient: Patient,
  utterance: string,
  response: string,
  category: string,
  priority: Priority,
  priorityLabel: string,
  route: string,
  workflow: "escalation" | "delivery",
): ConversationEntry[] {
  return [
    { kind: "system", text: "ロボットが病室の巡回を開始しました" },
    { kind: "system", text: `${patient.name}（${patient.room}）を発見しました` },
    { kind: "robot", text: "体調はいかがですか？" },
    { kind: "patient", text: utterance, initial: patient.name.charAt(0) },
    { kind: "classification", category, priority, priorityLabel, route },
    { kind: "robot-audio", text: response },
    {
      kind: "complete",
      text: workflow === "delivery" ? "配送ワークフローに接続しました" : "エスカレーションを作成しました",
    },
  ];
}

type HistorySeed = {
  patientId: string;
  hoursAgo: number;
  utterance: string;
  category: string;
  priority: Priority;
  route: string;
  response: string;
  workflow: "escalation" | "delivery";
};

const HISTORY_SEEDS: HistorySeed[] = [
  {
    patientId: "p1",
    hoursAgo: 0.4,
    utterance: "トイレに行きたいです",
    category: "排泄介助",
    priority: "urgent",
    route: "介護スタッフへ即時通知",
    response: "かしこまりました。すぐに介護スタッフにお伝えします。少々お待ちください。",
    workflow: "escalation",
  },
  {
    patientId: "p1",
    hoursAgo: 2.5,
    utterance: "喉が渇きました、お水がほしいです",
    category: "飲食物リクエスト",
    priority: "normal",
    route: "配膳ワークフローに接続",
    response: "かしこまりました。お飲み物をお届けする手配をいたします。",
    workflow: "delivery",
  },
  {
    patientId: "p1",
    hoursAgo: 20,
    utterance: "特に用事はありません、少し話し相手が欲しいだけです",
    category: "その他・会話",
    priority: "normal",
    route: "記録として保存",
    response: "お話しいただきありがとうございます。またいつでもお声がけください。",
    workflow: "escalation",
  },
  {
    patientId: "p2",
    hoursAgo: 1.2,
    utterance: "お薬の時間について聞きたいです",
    category: "服薬案内",
    priority: "normal",
    route: "記録として保存",
    response: "お薬の時間になりましたら改めてお知らせいたします。",
    workflow: "escalation",
  },
  {
    patientId: "p2",
    hoursAgo: 50,
    utterance: "体位を変えてもらいたいです",
    category: "体位交換",
    priority: "normal",
    route: "介護スタッフへ通知",
    response: "承知しました。介護スタッフが体位交換のお手伝いに伺います。",
    workflow: "escalation",
  },
  {
    patientId: "p3",
    hoursAgo: 5,
    utterance: "点滴の様子を見てほしいです",
    category: "点滴確認",
    priority: "urgent",
    route: "看護師へエスカレーション",
    response: "かしこまりました。看護師が点滴の状態を確認しに伺います。",
    workflow: "escalation",
  },
  {
    patientId: "p4",
    hoursAgo: 130,
    utterance: "お腹が痛いです",
    category: "体調不良",
    priority: "urgent",
    route: "看護師へエスカレーション",
    response:
      "承知しました。ただちに看護師へ連絡します。無理をせず楽な姿勢でお待ちください。",
    workflow: "escalation",
  },
];

export function seedHistory(): HistoryRecord[] {
  const now = Date.now();
  return HISTORY_SEEDS.map((sd, i) => {
    const patient = PATIENTS.find((p) => p.id === sd.patientId) ?? PATIENTS[0];
    const meta = PRIORITY_META[sd.priority];
    return {
      id: `h${i}`,
      patientId: sd.patientId,
      timestamp: now - sd.hoursAgo * 3600 * 1000,
      summary: sd.utterance,
      priority: sd.priority,
      priorityLabel: meta.label,
      entries: buildHistoryEntries(
        patient,
        sd.utterance,
        sd.response,
        sd.category,
        sd.priority,
        meta.label,
        sd.route,
        sd.workflow,
      ),
    };
  });
}

export const HISTORY_BUCKET_DEFS = [
  { label: "直近1時間", max: 1 },
  { label: "直近3時間", max: 3 },
  { label: "直近1日", max: 24 },
  { label: "直近1週間", max: 168 },
  { label: "それ以前", max: Infinity },
];

export function timeLabelFor(hoursAgo: number): string {
  if (hoursAgo < 1) return `${Math.max(1, Math.round(hoursAgo * 60))}分前`;
  if (hoursAgo < 24) return `${Math.round(hoursAgo)}時間前`;
  return `${Math.round(hoursAgo / 24)}日前`;
}

export function fmtTime(d: Date): string {
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

/**
 * Wall-clock/random reads live here (outside the component) so React's
 * render-purity lint rule doesn't see them as impure calls inside a component body.
 */
export function currentTimestamp(): number {
  return Date.now();
}

function randomId(prefix: string): string {
  return prefix + Date.now() + Math.random().toString(36).slice(2, 6);
}

export function pickRandomScenario(): { utterance: string; moodLevel: MoodLevel } {
  const utterance = SAMPLE_PHRASES[Math.floor(Math.random() * SAMPLE_PHRASES.length)];
  const moodLevel = MOOD_LEVELS[Math.floor(Math.random() * MOOD_LEVELS.length)];
  return { utterance, moodLevel };
}

export function buildEscalation(
  patient: { name: string; room: string },
  request: string,
  priority: Priority,
): Escalation {
  return {
    id: randomId("e"),
    patient: patient.name,
    room: patient.room,
    request,
    priority,
    time: fmtTime(new Date(currentTimestamp())),
    status: "active",
    assignedNurse: null,
  };
}

export function buildHistoryRecordFromRun(
  patientId: string,
  utterance: string,
  priority: Priority,
  entries: ConversationEntry[],
): HistoryRecord {
  return {
    id: randomId("h"),
    patientId,
    timestamp: currentTimestamp(),
    summary: utterance,
    priority,
    priorityLabel: PRIORITY_META[priority].label,
    entries,
  };
}

export function buildRunEntries(
  patient: Patient,
  utterance: string,
  result: ClassificationResult,
  moodLabel: string,
): ConversationEntry[] {
  const meta = PRIORITY_META[result.priority];
  return [
    { kind: "system", text: "ロボットが病室の巡回を開始しました" },
    { kind: "system", text: `${patient.name}（${patient.room}）を発見しました` },
    { kind: "robot", text: "体調はいかがですか？" },
    { kind: "patient", text: utterance, initial: patient.name.charAt(0) },
    {
      kind: "classification",
      category: result.category,
      priority: result.priority,
      priorityLabel: meta.label,
      route: result.route,
      moodLabel,
      autoEscalated: !!result.autoEscalated,
    },
    { kind: "robot-audio", text: result.response },
    {
      kind: "complete",
      text:
        result.workflow === "delivery"
          ? "配送ワークフローに接続しました"
          : "エスカレーションを作成しました",
    },
  ];
}
