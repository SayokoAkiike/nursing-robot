# PreCare Dock — 共通スタイル・文言

# カラーパレット（モノトーン基調）
COLORS = {
    "primary":   "#111111",
    "secondary": "#555555",
    "muted":     "#999999",
    "border":    "#e0e0e0",
    "bg":        "#ffffff",
    "bg_soft":   "#f7f7f7",
    "warning":   "#b45309",
    "error":     "#b91c1c",
    "success":   "#166534",
    "accent":    "#2563eb",
}

# 文言
LABELS = {
    "app_patient":   "PreCare Request",
    "app_nurse":     "PreCare Console",
    "room":          "Room 203 — Patient A",
    "toileting":     "Toileting preparation",
    "water":         "Water request",
    "nurse_check":   "Nurse check",
    "wait_msg_ja":   "立ち上がらずお待ちください",
    "wait_msg_en":   "Please do not stand up.",
    "nurse_coming":  "A nurse will arrive shortly.",
}

# 共通CSS
CSS = """
<style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 720px; }
    h1, h2, h3 { font-weight: 600; color: #111111; }
    .stButton > button {
        border-radius: 6px;
        border: 1px solid #d0d0d0;
        background: #ffffff;
        color: #111111;
        font-size: 15px;
        padding: 0.6rem 1.2rem;
        transition: all 0.15s;
    }
    .stButton > button:hover {
        border-color: #111111;
        background: #f0f0f0;
    }
    .stButton > button[kind=primary] {
        background: #111111;
        color: #ffffff;
        border-color: #111111;
    }
    div[data-testid=stMetricValue] { font-size: 1rem; font-weight: 500; }
</style>
"""
