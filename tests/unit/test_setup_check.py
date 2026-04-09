"""
Unit tests for `setup_check.py`.

Test structure:

UNIT TESTS
0. Fixtures & Setup
1. Constructor & Initialization
2. Accessors (Getters / Setters)
3. Main Methods
4. Fundamental Behavior & Mathematical Properties
5. Special Cases & Tolerance
6. Regression & Non-Regression
"""

from __future__ import annotations

from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

import paramiko
import pytest

from orsync.setup_check import CheckItem, CheckReport, run_check

# ============================================================
# 0. FIXTURES & SETUP
# ============================================================


@pytest.fixture
def valid_config() -> dict:
    """Full configuration with USB and Wi-Fi."""
    return {
        "remarkable_ip_usb": "10.11.99.1",
        "remarkable_ip_wifi": "192.168.1.42",
        "ssh_key_path": "/home/user/.ssh/id_rsa_remarkable",
        "ssh_timeout": 2,
    }


@pytest.fixture
def config_without_wifi() -> dict:
    """This is a WiFi setup without an IP address, so the WiFi check should be skipped."""
    return {
        "remarkable_ip_usb": "10.11.99.1",
        "remarkable_ip_wifi": "",
        "ssh_key_path": "/home/user/.ssh/id_rsa_remarkable",
        "ssh_timeout": 2,
    }


@pytest.fixture
def mock_ssh_success():
    """Mock of paramiko.SSHClient simulating a successful SSH connection."""
    with patch("orsync.setup_check.paramiko.SSHClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.exec_command.return_value = (
            MagicMock(),
            MagicMock(read=lambda: b"3.11.2.4"),
            MagicMock(),
        )
        yield mock_client


@pytest.fixture
def mock_ssh_only_wifi_success():
    """Mock simulating USB SSH failure and WiFi SSH success."""
    call_count = 0

    with patch("orsync.setup_check.paramiko.SSHClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("USB not available")
            return None

        mock_client.connect.side_effect = side_effect
        mock_client.exec_command.return_value = (
            MagicMock(),
            MagicMock(read=lambda: b"3.11.2.4"),
            MagicMock(),
        )
        yield mock_client


@pytest.fixture
def mock_ssh_failure():
    """Mock of paramiko.SSHClient simulating an SSH connection failure."""
    with patch("orsync.setup_check.paramiko.SSHClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.connect.side_effect = OSError("Connection refused")
        yield mock_client


@pytest.fixture
def mock_pandoc_found():
    """Mock simulating Pandoc in the PATH."""
    with (
        patch("orsync.setup_check.shutil.which", return_value="/usr/bin/pandoc"),
        patch("orsync.setup_check.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="pandoc 3.1.2\n")
        yield mock_run


@pytest.fixture
def mock_pandoc_missing():
    """Mock simulating Pandoc not in the PATH."""
    with patch("orsync.setup_check.shutil.which", return_value=None):
        yield


@pytest.fixture
def mock_pandoc_non_zero_exit_code():
    """Mock simulating Pandoc return a non-zero exit code."""
    with (
        patch("orsync.setup_check.shutil.which", return_value="/usr/bin/pandoc"),
        patch("orsync.setup_check.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        yield mock_run


@pytest.fixture
def mock_pandoc_timeout():
    """Mock simulating Pandoc timeout."""
    with (
        patch("orsync.setup_check.shutil.which", return_value="/usr/bin/pandoc"),
        patch(
            "orsync.setup_check.subprocess.run", side_effect=TimeoutExpired(cmd="pandoc", timeout=5)
        ),
    ):
        yield


# ============================================================
# 1. CONSTRUCTOR & INITIALIZATION
# ============================================================


def test_constructor_item_name_stored_correctly():
    """item.name must be stored as a string with the correct value."""
    item = CheckItem(name="test", status=True, detail="ok")
    assert isinstance(item.name, str)
    assert item.name == "test"


def test_constructor_item_status_stored_correctly():
    """item.status must be stored as a boolean with the correct value."""
    item = CheckItem(name="test", status=True, detail="ok")
    assert isinstance(item.status, bool)
    assert item.status is True


def test_constructor_item_detail_stored_correctly():
    """item.detail must be stored as a string with the correct value."""
    item = CheckItem(name="test", status=True, detail="ok")
    assert isinstance(item.detail, str)
    assert item.detail == "ok"


def test_constructor_report_all_ok_true_when_empty():
    """all_ok must return True for an empty report (vacuous truth)."""
    report = CheckReport()
    assert report.all_ok is True


def test_constructor_check_report_all_ok_true_when_all_items_pass():
    """all_ok must return True when every CheckItem has status=True."""
    report = CheckReport(
        items=[
            CheckItem("A", True, "ok"),
            CheckItem("B", True, "ok"),
            CheckItem("C", True, "ok"),
            CheckItem("D", True, "ok"),
            CheckItem("E", True, "ok"),
        ]
    )
    assert report.all_ok is True


def test_constructor_check_report_all_ok_false_when_any_item_fails():
    """all_ok must return False when at least one CheckItem has status=False."""
    report = CheckReport(
        items=[
            CheckItem("A", True, "ok"),
            CheckItem("B", True, "ok"),
            CheckItem("C", True, "ok"),
            CheckItem("D", True, "ok"),
            CheckItem("E", False, "failed"),
        ]
    )
    assert report.all_ok is False


# ============================================================
# 2. ACCESSORS (GETTERS / SETTERS)
# ============================================================


def test_item_str_valid_status_contains_success_symbol():
    """__str__ must contain SUCCESS and ✅ when status is True."""
    item = CheckItem(name="Pandoc", status=True, detail="pandoc 3.1.2")
    assert "SUCCESS" in str(item)
    assert "✅" in str(item)


def test_item_str_invalid_status_contains_error_symbol():
    """__str__ must contain ERROR and ❌ when status is False."""
    item = CheckItem(name="Pandoc", status=False, detail="not found")
    assert "ERROR" in str(item)
    assert "❌" in str(item)


def test_item_str_contains_name_and_detail():
    """__str__ must include the item name and detail message."""
    item = CheckItem(name="SSH USB connection", status=True, detail="connected to root@10.11.99.1")
    result = str(item)
    assert "SSH USB connection" in result
    assert "connected to root@10.11.99.1" in result


def test_repr_report_valid_status_case():
    """print_report must contain all result of the report (test case with valid status)"""
    report = CheckReport(items=[CheckItem(name="Pandoc", status=True, detail="pandoc 3.1.2")])
    r = repr(report)
    assert "Installation Check" in r
    assert "Pandoc" in r
    assert "SUCCESS" in r
    assert "pandoc 3.1.2" in r
    assert "All checks passed ✅" in r


def test_repr_report_invalid_status_case():
    """print_report must contain all result of the report (test case with invalid status)"""
    report = CheckReport(items=[CheckItem(name="Pandoc", status=False, detail="not found")])
    r = repr(report)
    assert "Installation Check" in r
    assert "Pandoc" in r
    assert "ERROR" in r
    assert "not found" in r
    assert "Some checks failed ❌" in r


# ============================================================
# 3. MAIN METHODS
# ============================================================


def test_run_check_detects_os(mock_pandoc_found, mock_ssh_success, valid_config):
    """run_check must include an OS detection item with status=True."""
    report = run_check(valid_config)
    os_items = [i for i in report.items if i.name == "OS detected"]
    assert len(os_items) == 1
    assert os_items[0].status is True
    assert os_items[0].detail != ""


def test_run_check_pandoc_found_returns_success(mock_pandoc_found, mock_ssh_success, valid_config):
    """run_check must report Pandoc as success when shutil.which finds it."""
    report = run_check(valid_config)
    pandoc_items = [i for i in report.items if i.name == "Pandoc"]
    assert len(pandoc_items) == 1
    assert pandoc_items[0].status is True
    assert "pandoc" in pandoc_items[0].detail.lower()


def test_run_check_pandoc_missing_returns_failure(
    mock_pandoc_missing, mock_ssh_success, valid_config
):
    """run_check must report Pandoc as failure when not found in PATH."""
    report = run_check(valid_config)
    pandoc_items = [i for i in report.items if i.name == "Pandoc"]
    assert len(pandoc_items) == 1
    assert pandoc_items[0].status is False
    assert "PATH" in pandoc_items[0].detail


def test_run_check_pandoc_returns_non_zero_exit_code(
    mock_pandoc_non_zero_exit_code, mock_ssh_success, valid_config
):
    """run_check must report Pandoc as failure when found but return non-zero exit code."""
    report = run_check(valid_config)
    pandoc_items = [i for i in report.items if i.name == "Pandoc"]
    assert len(pandoc_items) == 1
    assert pandoc_items[0].status is False
    assert "non-zero exit code" in pandoc_items[0].detail


def test_run_check_pandoc_timeout_returns_failure(
    mock_pandoc_timeout, mock_ssh_success, valid_config
):
    """run_check must report Pandoc as failure when pandoc timeout appears on --version."""
    report = run_check(valid_config)
    pandoc_items = [i for i in report.items if i.name == "Pandoc"]
    assert len(pandoc_items) == 1
    assert pandoc_items[0].status is False
    assert "timed out" in pandoc_items[0].detail


def test_run_check_ssh_usb_success_returns_success(
    mock_pandoc_found, mock_ssh_success, valid_config
):
    """run_check must report SSH USB as success when paramiko connects."""
    report = run_check(valid_config)
    usb_items = [i for i in report.items if i.name == "SSH USB connection"]
    assert len(usb_items) == 1
    assert usb_items[0].status is True


def test_run_check_ssh_wifi_success_returns_success(
    mock_pandoc_found, mock_ssh_success, valid_config
):
    """run_check must report SSH WiFi as success when paramiko connects."""
    report = run_check(valid_config)
    wifi_items = [i for i in report.items if i.name == "SSH WiFi connection"]
    assert len(wifi_items) == 1
    assert wifi_items[0].status is True


def test_run_check_retrieves_firmware_version_on_success_with_usb(
    mock_pandoc_found, mock_ssh_success, valid_config
):
    """run_check must include a firmware item (with usb connection)"""
    report = run_check(valid_config)
    fw_items = [i for i in report.items if i.name == "reMarkable firmware"]
    assert len(fw_items) == 1
    assert fw_items[0].status is True
    assert fw_items[0].detail != ""


def test_run_check_firmware_via_wifi_when_usb_fails(
    mock_pandoc_found, mock_ssh_only_wifi_success, valid_config
):
    """run_check must include a firmware item with wifi connection (usb fail)."""
    report = run_check(valid_config)
    fw_items = [i for i in report.items if i.name == "reMarkable firmware"]
    assert len(fw_items) == 1
    assert fw_items[0].status is True
    assert fw_items[0].detail != ""


def test_run_check_returns_five_items_with_wifi(mock_pandoc_found, mock_ssh_success, valid_config):
    """run_check must return exactly 5 CheckItems when WiFi IP is configured."""
    report = run_check(valid_config)
    assert len(report.items) == 5


def test_run_check_returns_five_items_without_wifi(
    mock_pandoc_found, mock_ssh_success, config_without_wifi
):
    """run_check must return exactly 5 CheckItems even when WiFi is skipped."""
    report = run_check(config_without_wifi)
    assert len(report.items) == 5


# ============================================================
# 4. FUNDAMENTAL BEHAVIOR & MATHEMATICAL PROPERTIES
# ============================================================


def test_run_check_ssh_failure_does_not_raise_exception(
    mock_pandoc_found, mock_ssh_failure, valid_config
):
    """run_check must never raise even when SSH connection fails."""
    report = run_check(valid_config)
    assert isinstance(report, CheckReport)


def test_run_check_wifi_failure_does_not_block_usb_check(mock_pandoc_found, valid_config):
    """A WiFi SSH failure must not prevent the USB check from running."""
    call_count = 0

    def side_effect_by_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return None  # USB succeeds
        raise OSError("WiFi timeout")  # WiFi fails

    with patch("orsync.setup_check.paramiko.SSHClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.connect.side_effect = side_effect_by_call
        mock_client.exec_command.return_value = (
            MagicMock(),
            MagicMock(read=lambda: b"3.11.2.4"),
            MagicMock(),
        )
        report = run_check(valid_config)

    usb_items = [i for i in report.items if i.name == "SSH USB connection"]
    assert usb_items[0].status is True


def test_run_check_firmware_skipped_if_both_ssh_fail(
    mock_pandoc_found, mock_ssh_failure, valid_config
):
    """Firmware check must be skipped (status=False, detail='skipped') when all SSH fail."""
    report = run_check(valid_config)
    fw_items = [i for i in report.items if i.name == "reMarkable firmware"]
    assert len(fw_items) == 1
    assert fw_items[0].status is False
    assert "skipped" in fw_items[0].detail.lower()


# ============================================================
# 5. SPECIAL CASES & TOLERANCE
# ============================================================


def test_run_check_no_wifi_ip_skips_wifi_check(
    mock_pandoc_found, mock_ssh_success, config_without_wifi
):
    """WiFi check must be reported as skipped when ip_wifi is empty."""
    report = run_check(config_without_wifi)
    wifi_items = [i for i in report.items if i.name == "SSH WiFi connection"]
    assert len(wifi_items) == 1
    assert wifi_items[0].status is True
    assert "skipped" in wifi_items[0].detail.lower()


def test_run_check_ssh_timeout_recorded_as_failure(mock_pandoc_found, valid_config):
    """A connection timeout must be recorded as a failed CheckItem, not raised."""
    with patch("orsync.setup_check.paramiko.SSHClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.connect.side_effect = TimeoutError("timed out")
        report = run_check(valid_config)

    usb_items = [i for i in report.items if i.name == "SSH USB connection"]
    assert usb_items[0].status is False
    assert "timed" in usb_items[0].detail.lower() or "connect" in usb_items[0].detail.lower()


def test_run_check_authentication_failure_recorded_as_failure(mock_pandoc_found, valid_config):
    """An SSH AuthenticationException must be recorded as failure with actionable detail."""
    with patch("orsync.setup_check.paramiko.SSHClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.connect.side_effect = paramiko.AuthenticationException()
        report = run_check(valid_config)

    usb_items = [i for i in report.items if i.name == "SSH USB connection"]
    assert usb_items[0].status is False
    assert "key" in usb_items[0].detail.lower() or "auth" in usb_items[0].detail.lower()


def test_run_check_missing_ssh_key_recorded_as_failure(mock_pandoc_found, valid_config):
    """A missing SSH key file must be recorded as failure with the key path in detail."""
    with patch("orsync.setup_check.paramiko.SSHClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.connect.side_effect = FileNotFoundError("key not found")
        report = run_check(valid_config)

    usb_items = [i for i in report.items if i.name == "SSH USB connection"]
    assert usb_items[0].status is False
    assert valid_config["ssh_key_path"] in usb_items[0].detail


# ============================================================
# 6. REGRESSION & NON-REGRESSION
# ============================================================
# This section contains tests added after bug fixes.
# The goal is to ensure that previously identified issues never
# reappear in future changes.
#
# If no prior bugs or regressions have been identified,
# this section remains empty until needed.
# ============================================================
