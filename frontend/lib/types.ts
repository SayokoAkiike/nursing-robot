export type Priority = "urgent" | "normal";

export type Patient = {
  id: string;
  name: string;
  room: string;
};

export type QuickRequestKind =
  | "toilet"
  | "drip"
  | "reposition"
  | "suction"
  | "medicine"
  | "water";

export type QuickRequest = {
  label: string;
  phrase: string;
  kind: QuickRequestKind;
};

export type MoodId = "worst" | "bad" | "neutral" | "good" | "great";

export type MoodLevel = {
  id: MoodId;
  label: string;
  score: number;
  hue: number;
};

export type ScheduleStatus = "done" | "upcoming";

export type ScheduleItem = {
  time: string;
  task: string;
  note: string;
  status: ScheduleStatus;
};

export type ClassificationResult = {
  category: string;
  priority: Priority;
  route: string;
  response: string;
  workflow: "escalation" | "delivery";
  autoEscalated?: boolean;
  vasScore: number | null;
  moodLabel?: string;
};

/** Mirrors the `kind`-tagged entries the design's conversation log renders. */
export type ConversationEntry =
  | { kind: "system"; text: string }
  | { kind: "robot"; text: string }
  | { kind: "robot-audio"; text: string }
  | { kind: "patient"; text: string; initial: string }
  | {
      kind: "classification";
      category: string;
      priority: Priority;
      priorityLabel: string;
      route: string;
      moodLabel?: string;
      autoEscalated?: boolean;
    }
  | { kind: "complete"; text: string };

export type EscalationStatus = "active" | "acknowledged" | "resolved";

export type Escalation = {
  id: string;
  patient: string;
  room: string;
  request: string;
  priority: Priority;
  time: string;
  status: EscalationStatus;
  assignedNurse: string | null;
};

export type HistoryRecord = {
  id: string;
  patientId: string;
  timestamp: number;
  summary: string;
  priority: Priority;
  priorityLabel: string;
  entries: ConversationEntry[];
};

export type DeviceType = "bedside" | "robot" | "nurse";

export type ChatMessage = {
  from: "patient" | "nurse";
  text: string;
};
