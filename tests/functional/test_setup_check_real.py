"""
Functional tests for `setup_check.py`.

Run with: pytest tests/functional/ --functional --no-cov -s

Prerequisites:
  - Real hardware is required.
  - reMarkable connected via USB (10.11.99.1)
  - SSH key deployed on the tablet
  - Pandoc installed
"""

from orsync.setup_check import run_check


def _prompt(message: str) -> None:
    """Pause the test and wait for the user to press Enter."""
    input(f"\n[ACTION REQUIRED] {message}\nPress Enter to continue...")


# ============================================================
# 1. NOMINAL — tablet connected
# ============================================================


def test_full_check_passes_when_tablet_connected(real_config):
    """All checks must pass on a nominal setup (tablet connected, Pandoc installed)."""
    _prompt("Make sure the reMarkable is connected via USB and Pandoc is installed.")
    report = run_check(real_config)
    failed = [i for i in report.items if not i.status]
    assert report.all_ok, f"Failed checks: {[i.name for i in failed]}"


def test_firmware_version_is_non_empty(real_config):
    """Firmware version read over SSH must be a non-empty string."""
    _prompt("Make sure the reMarkable is connected via USB.")
    report = run_check(real_config)
    fw = next(i for i in report.items if i.name == "reMarkable firmware")
    assert fw.status is True
    assert fw.detail.strip() != ""


# ============================================================
# 2. DEGRADED — tablet disconnected
# ============================================================


def test_ssh_fails_gracefully_when_tablet_disconnected(real_config):
    """SSH check must return status=False with a non-empty detail when the tablet is unplugged."""
    _prompt("Unplug the reMarkable tablet now.")
    report = run_check(real_config)
    usb = next(i for i in report.items if i.name == "SSH USB connection")
    assert usb.status is False
    assert usb.detail.strip() != ""


def test_all_ok_is_false_when_tablet_disconnected(real_config):
    """all_ok must be False when SSH cannot connect."""
    report = run_check(real_config)
    assert report.all_ok is False


# ============================================================
# 3. RECOVERY — tablet reconnected
# ============================================================


def test_check_recovers_after_reconnection(real_config):
    """run_check must pass again after the tablet is reconnected."""
    _prompt("Plug the reMarkable back in and wait a few seconds for the connection to stabilise.")
    report = run_check(real_config)
    assert (
        report.all_ok
    ), f"Failed after reconnection: {[i.name for i in report.items if not i.status]}"
