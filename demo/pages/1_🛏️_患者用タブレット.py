import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from ui.common.backend_bootstrap import start_backend  # noqa: E402

start_backend()

from ui.patient_request_app.app import main  # noqa: E402

main()
