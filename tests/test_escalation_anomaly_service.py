"""Tests for backend/services/escalation_anomaly_service.py.

No mocking needed -- unlike faster-whisper/mediapipe/sentence-transformers
/llama-cpp-python, scikit-learn is a normal pip package with no network
download at use time (only at install time, already satisfied as a
transitive dependency of sentence-transformers, and now also a direct
one -- see requirements.txt). Every test here runs the real
IsolationForest.
"""
from datetime import datetime, timedelta

from backend.services.escalation_anomaly_service import (
    MIN_PATIENTS_FOR_ANALYSIS,
    AnomalyResult,
    PatientEscalationFeatures,
    analyze,
    compute_patient_features,
    detect_anomalies,
)


def _escalation_row(patient_id, priority="MEDIUM", created_at=None, acknowledged_at=None):
    return {
        "patient_id": patient_id,
        "priority": priority,
        "created_at": created_at or datetime(2026, 7, 1, 9, 0, 0),
        "acknowledged_at": acknowledged_at,
    }


# ---- compute_patient_features ------------------------------------------------


def test_compute_patient_features_groups_by_patient_id():
    escalations = [
        _escalation_row("PATIENT_A", priority="HIGH"),
        _escalation_row("PATIENT_A", priority="URGENT"),
        _escalation_row("PATIENT_B", priority="LOW"),
    ]
    features = compute_patient_features(escalations)
    by_id = {f.patient_id: f for f in features}

    assert by_id["PATIENT_A"].escalation_count == 2
    assert by_id["PATIENT_A"].urgent_count == 1
    assert by_id["PATIENT_B"].escalation_count == 1
    assert by_id["PATIENT_B"].urgent_count == 0


def test_compute_patient_features_skips_rows_with_no_patient_id():
    escalations = [_escalation_row(None), _escalation_row("PATIENT_A")]
    features = compute_patient_features(escalations)
    assert len(features) == 1
    assert features[0].patient_id == "PATIENT_A"


def test_compute_patient_features_avg_priority_score():
    escalations = [
        _escalation_row("PATIENT_A", priority="LOW"),  # 1.0
        _escalation_row("PATIENT_A", priority="URGENT"),  # 4.0
    ]
    features = compute_patient_features(escalations)
    assert features[0].avg_priority_score == 2.5


def test_compute_patient_features_avg_time_to_ack_only_uses_acked_rows():
    created = datetime(2026, 7, 1, 9, 0, 0)
    acked = created + timedelta(seconds=120)
    escalations = [
        _escalation_row("PATIENT_A", created_at=created, acknowledged_at=acked),
        _escalation_row("PATIENT_A", created_at=created, acknowledged_at=None),  # still pending
    ]
    features = compute_patient_features(escalations)
    assert features[0].avg_time_to_ack_seconds == 120.0


def test_compute_patient_features_no_acked_rows_is_none():
    escalations = [_escalation_row("PATIENT_A", acknowledged_at=None)]
    features = compute_patient_features(escalations)
    assert features[0].avg_time_to_ack_seconds is None


def test_compute_patient_features_empty_input():
    assert compute_patient_features([]) == []


# ---- detect_anomalies ---------------------------------------------------------


def _normal_features(patient_id: str) -> PatientEscalationFeatures:
    return PatientEscalationFeatures(
        patient_id=patient_id,
        escalation_count=2,
        urgent_count=0,
        avg_priority_score=2.0,
        avg_time_to_ack_seconds=180.0,
    )


def test_detect_anomalies_returns_empty_below_min_patients():
    features = [_normal_features(f"P{i}") for i in range(MIN_PATIENTS_FOR_ANALYSIS - 1)]
    assert detect_anomalies(features) == []


def test_detect_anomalies_returns_one_result_per_patient_at_min_threshold():
    features = [_normal_features(f"P{i}") for i in range(MIN_PATIENTS_FOR_ANALYSIS)]
    results = detect_anomalies(features)
    assert len(results) == MIN_PATIENTS_FOR_ANALYSIS
    assert all(isinstance(r, AnomalyResult) for r in results)


def test_detect_anomalies_flags_a_clear_outlier():
    """Several near-identical patients plus one wildly different one --
    the outlier should be flagged, the uniform ones should not."""
    features = [_normal_features(f"P{i}") for i in range(8)]
    outlier = PatientEscalationFeatures(
        patient_id="OUTLIER",
        escalation_count=50,
        urgent_count=40,
        avg_priority_score=4.0,
        avg_time_to_ack_seconds=9000.0,
    )
    features.append(outlier)

    results = detect_anomalies(features)
    by_id = {r.patient_id: r for r in results}

    assert by_id["OUTLIER"].is_anomalous is True
    # At least the uniform group's majority should NOT be flagged --
    # avoids a brittle "every single one" assertion while still checking
    # the model isn't just flagging everyone.
    normal_flagged = sum(1 for i in range(8) if by_id[f"P{i}"].is_anomalous)
    assert normal_flagged <= 2


def test_detect_anomalies_is_deterministic():
    features = [_normal_features(f"P{i}") for i in range(6)]
    features.append(
        PatientEscalationFeatures(
            patient_id="ODD", escalation_count=20, urgent_count=15, avg_priority_score=3.8, avg_time_to_ack_seconds=5000.0
        )
    )
    first = detect_anomalies(features)
    second = detect_anomalies(features)
    assert [(r.patient_id, r.is_anomalous, r.anomaly_score) for r in first] == [
        (r.patient_id, r.is_anomalous, r.anomaly_score) for r in second
    ]


def test_detect_anomalies_handles_none_ack_time_in_feature_vector():
    """A patient with no acknowledged escalations yet (avg_time_to_ack_seconds
    is None) must not crash the feature matrix construction."""
    features = [_normal_features(f"P{i}") for i in range(4)] + [
        PatientEscalationFeatures(
            patient_id="PENDING_ONLY", escalation_count=1, urgent_count=0, avg_priority_score=2.0, avg_time_to_ack_seconds=None
        )
    ]
    results = detect_anomalies(features)
    assert len(results) == 5


# ---- analyze() (full pipeline) -------------------------------------------------


def test_analyze_on_empty_db_returns_zero_patients_no_error():
    result = analyze()
    assert result["total_patients_analyzed"] == 0
    assert result["anomalous_patients"] == []


def test_analyze_never_raises_below_min_patients(monkeypatch):
    monkeypatch.setattr(
        "backend.services.escalation_anomaly_service.repositories.list_nurse_escalations",
        lambda status=None: [_escalation_row("PATIENT_A"), _escalation_row("PATIENT_B")],
    )
    result = analyze()
    assert result["total_patients_analyzed"] == 2
    assert result["anomalous_patients"] == []


def test_analyze_surfaces_an_anomalous_patient(monkeypatch):
    created = datetime(2026, 7, 1, 9, 0, 0)
    rows = []
    for i in range(6):
        rows.append(_escalation_row(f"PATIENT_{i}", priority="MEDIUM", created_at=created))
    # One patient with many more, higher-priority escalations than everyone else.
    for _ in range(15):
        rows.append(_escalation_row("PATIENT_OUTLIER", priority="URGENT", created_at=created))

    monkeypatch.setattr(
        "backend.services.escalation_anomaly_service.repositories.list_nurse_escalations",
        lambda status=None: rows,
    )
    result = analyze()

    assert result["total_patients_analyzed"] == 7
    anomalous_ids = {p["patient_id"] for p in result["anomalous_patients"]}
    assert "PATIENT_OUTLIER" in anomalous_ids
