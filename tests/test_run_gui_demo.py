"""Safety/static tests for PR20's GUI demo entrypoint.

p.GUI requires a real display -- not available in CI or Codespaces -- so
this file deliberately never calls run_demo() with a valid preset (that
would try to open a window and hang/fail). It only exercises the parts
that are safe headlessly: argument validation that happens before
p.connect(p.GUI) is ever called, and that the CLI wiring passes the right
values through (with run_demo() itself patched out).
"""
import pytest

from backend.scripts import run_gui_demo


@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"preset": "does-not-exist"}, "Unknown PyBullet scene preset"),
        ({"steps": 0}, "steps must be"),
        ({"speed": 0}, "speed must be"),
        ({"speed": -1.0}, "speed must be"),
    ],
)
def test_invalid_arguments_raise_before_touching_pybullet(kwargs, message):
    """All of these must fail before p.connect(p.GUI) is ever called --
    that's what makes it safe to test in a headless environment."""
    with pytest.raises(ValueError, match=message):
        run_gui_demo.run_demo(**kwargs)


def test_cli_passes_parsed_arguments_through_to_run_demo(monkeypatch):
    """argparse wiring is exercised without ever calling the real
    run_demo() (patched out), since that would try to open a GUI window."""
    calls = []
    monkeypatch.setattr(run_gui_demo, "run_demo", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(
        "sys.argv", ["run_gui_demo.py", "--preset", "delivery", "--steps", "10", "--speed", "2.0"]
    )
    run_gui_demo.main()
    assert calls == [{"preset": "delivery", "steps": 10, "speed": 2.0}]


def test_cli_defaults(monkeypatch):
    calls = []
    monkeypatch.setattr(run_gui_demo, "run_demo", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr("sys.argv", ["run_gui_demo.py"])
    run_gui_demo.main()
    assert calls == [{"preset": "delivery", "steps": 120, "speed": 1.0}]
