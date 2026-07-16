import type { Priority } from "./types";

/**
 * Client-side counterpart to `demo/pages/3_🚶_巡回・要望分類デモ.py`: drives
 * the same `backend/services/rounding_service.py` state machine (via the
 * `/api/rounding/[...path]` proxy) instead of a local keyword-matching mock,
 * so the robot screen's patrol/need-classification demo reflects whatever
 * `backend/services/need_classification_service.py` actually decides.
 */

const NEED_LABELS_JA: Record<string, string> = {
  pain: "強い痛み・苦しさ",
  fall_risk: "転倒の危険（ふらつき・一人での立ち上がり）",
  toileting: "トイレ介助",
  nurse_check: "看護師の訪室",
  water: "飲水介助",
  anxiety: "不安・不眠",
  position_change: "体位変換",
  temperature: "室温調整",
  information_only: "特になし",
  unknown: "内容不明",
};

const ROUTE_ACK_TEXT: Record<string, string> = {
  INFORMATION_ONLY: "承知しました。またいつでもお声がけくださいね。",
  NURSE_NOTIFICATION: "承知しました。看護師にお伝えしますね。少々お待ちください。",
  URGENT_ESCALATION: "すぐに看護師へお伝えします。無理をせず、そのままお待ちください。",
  DELIVERY_REQUIRED: "かしこまりました。お届けする手配をいたします。",
};

export type RoundingWorkflow = "escalation" | "delivery" | "information";

export type RoundingOutcome = {
  sessionId: string;
  prompt: string;
  utterance: string;
  detectedNeed: string;
  needLabel: string;
  escalationLevel: string;
  priority: Priority;
  route: string;
  summary: string;
  suggestedAction: string;
  ackText: string;
  workflow: RoundingWorkflow;
};

class RoundingApiError extends Error {}

async function roundingFetch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/rounding/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new RoundingApiError(
      data?.error ?? data?.detail ?? `巡回APIの呼び出しに失敗しました（${res.status}）`,
    );
  }
  return data as T;
}

function priorityFromEscalationLevel(level: string): Priority {
  return level === "URGENT" ? "urgent" : "normal";
}

/**
 * Runs one full rounding interaction against the real backend: start ->
 * detect-patient -> start-interaction -> classify-need, then whichever of
 * provide-information / escalate / require-delivery the classification's
 * `route` points to -- the same branch `demo/pages/3_🚶_巡回・要望分類デモ.py`
 * takes.
 */
export async function runRoundingInteraction(params: {
  room: string;
  patientId: string;
  patientResponse: string;
  inputMode?: "simulated" | "voice";
}): Promise<RoundingOutcome> {
  const { room, patientId, patientResponse, inputMode = "simulated" } = params;

  const started = await roundingFetch<{ rounding_session_id: string }>("start", { room });
  const sessionId = started.rounding_session_id;

  await roundingFetch(`${sessionId}/detect-patient`, { patient_id: patientId });

  const interaction = await roundingFetch<{ prompt: string }>(`${sessionId}/start-interaction`);

  const classification = await roundingFetch<{
    detected_need: string;
    escalation_level: string;
    route: string;
    summary: string;
    suggested_action: string;
  }>(`${sessionId}/classify-need`, {
    patient_response: patientResponse,
    input_mode: inputMode,
  });

  const route = classification.route;
  let workflow: RoundingWorkflow;
  if (route === "NURSE_NOTIFICATION" || route === "URGENT_ESCALATION") {
    await roundingFetch(`${sessionId}/escalate`, {
      summary: classification.summary,
      priority: classification.escalation_level,
      suggested_action: classification.suggested_action,
      reason: classification.detected_need,
      route,
    });
    workflow = "escalation";
  } else if (route === "DELIVERY_REQUIRED") {
    await roundingFetch(`${sessionId}/require-delivery`, {
      request_type: classification.detected_need,
      patient_id: patientId,
    });
    workflow = "delivery";
  } else {
    await roundingFetch(`${sessionId}/provide-information`);
    workflow = "information";
  }

  return {
    sessionId,
    prompt: interaction.prompt,
    utterance: patientResponse,
    detectedNeed: classification.detected_need,
    needLabel: NEED_LABELS_JA[classification.detected_need] ?? classification.detected_need,
    escalationLevel: classification.escalation_level,
    priority: priorityFromEscalationLevel(classification.escalation_level),
    route,
    summary: classification.summary,
    suggestedAction: classification.suggested_action,
    ackText: ROUTE_ACK_TEXT[route] ?? "承知しました。",
    workflow,
  };
}

export function roomNumberFor(room: string): string {
  return room.replace(/号室$/, "");
}
