import { EscalationsTab, type EscalationVm } from "@/components/nurse/escalations-tab";
import { PatientsTab, type PatientOverviewVm } from "@/components/nurse/patients-tab";
import { RobotHistoryTab, type HistoryBucketVm } from "@/components/nurse/robot-history-tab";
import type { PatientOption } from "@/components/bedside/bedside-screen";
import type { ConversationEntry } from "@/lib/types";

export type NurseSubTab = "patients" | "escalations" | "robot";

export function NurseScreen({
  subTab,
  onSetSubTab,
  patientOverviews,
  dashTab,
  onSetDashTab,
  activeCount,
  resolvedCount,
  visibleEscalations,
  patients,
  nurseRobotPatientId,
  onSelectNurseRobotPatient,
  historyMode,
  hasNoHistory,
  historyBuckets,
  selectedRecordTimeLabel,
  selectedRecordEntries,
  onCloseHistoryDetail,
}: {
  subTab: NurseSubTab;
  onSetSubTab: (tab: NurseSubTab) => void;
  patientOverviews: PatientOverviewVm[];
  dashTab: "open" | "resolved";
  onSetDashTab: (tab: "open" | "resolved") => void;
  activeCount: number;
  resolvedCount: number;
  visibleEscalations: EscalationVm[];
  patients: PatientOption[];
  nurseRobotPatientId: string;
  onSelectNurseRobotPatient: (id: string) => void;
  historyMode: "list" | "detail";
  hasNoHistory: boolean;
  historyBuckets: HistoryBucketVm[];
  selectedRecordTimeLabel: string;
  selectedRecordEntries: ConversationEntry[];
  onCloseHistoryDetail: () => void;
}) {
  const tabBase =
    "flex-1 rounded-[8px] border-none px-3.5 py-[9px] text-[13.5px] font-semibold whitespace-nowrap cursor-pointer";
  const tabStyle = (active: boolean) =>
    active
      ? { background: "white", color: "oklch(0.25 0.01 265)", boxShadow: "0 1px 2px oklch(0 0 0 / 0.05)" }
      : { background: "transparent", color: "oklch(0.55 0.01 250)" };

  return (
    <div>
      <div
        className="mb-[22px] flex w-fit gap-1.5 rounded-[10px] p-1"
        style={{ background: "oklch(0.95 0.003 260)" }}
      >
        <button type="button" className={tabBase} style={tabStyle(subTab === "patients")} onClick={() => onSetSubTab("patients")}>
          患者一覧
        </button>
        <button type="button" className={tabBase} style={tabStyle(subTab === "escalations")} onClick={() => onSetSubTab("escalations")}>
          エスカレーション
        </button>
        <button type="button" className={tabBase} style={tabStyle(subTab === "robot")} onClick={() => onSetSubTab("robot")}>
          見守りロボット
        </button>
      </div>

      {subTab === "patients" && <PatientsTab patients={patientOverviews} />}

      {subTab === "escalations" && (
        <EscalationsTab
          dashTab={dashTab}
          onSetDashTab={onSetDashTab}
          activeCount={activeCount}
          resolvedCount={resolvedCount}
          escalations={visibleEscalations}
        />
      )}

      {subTab === "robot" && (
        <RobotHistoryTab
          patients={patients}
          selectedPatientId={nurseRobotPatientId}
          onSelectPatient={onSelectNurseRobotPatient}
          mode={historyMode}
          hasNoHistory={hasNoHistory}
          buckets={historyBuckets}
          selectedRecordTimeLabel={selectedRecordTimeLabel}
          selectedRecordEntries={selectedRecordEntries}
          onCloseDetail={onCloseHistoryDetail}
        />
      )}
    </div>
  );
}
