"""Guards for hosting: things that only break once the app runs on a Linux cloud host."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_requirements_use_headless_opencv():
    # Cloud Linux images have no desktop graphics libraries (libGL), so the regular
    # opencv-python wheel fails to import there; the app never opens a window anyway.
    requirements = (ROOT / "requirements.txt").read_text().split()
    assert any(r.startswith("opencv-python-headless==") for r in requirements)
    assert not any(r.startswith("opencv-python==") for r in requirements)
