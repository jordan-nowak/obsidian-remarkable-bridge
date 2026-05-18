from __future__ import annotations

import os
import platform
import shutil
import subprocess
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field

import paramiko

# ============================================================
# DATA CLASSES
# ============================================================


@dataclass
class CheckItem:
    """Result of a single installation check."""

    name: str
    status: bool
    detail: str

    def __str__(self) -> str:
        symbol = "SUCCESS ✅" if self.status else "ERROR   ❌"
        return f"[{symbol}] {self.name}: {self.detail}"


@dataclass
class CheckReport:
    """Aggregated result of all installation checks."""

    items: list[CheckItem] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        """Return True only if every check passed."""
        return all(item.status for item in self.items)

    def __repr__(self) -> str:
        items_repr = "".join(f"\n{item}" for item in self.items)
        overall = "All checks passed ✅" if self.all_ok else "Some checks failed ❌"
        return (
            f"\n__ Installation Check ______________________________________"
            f"  {items_repr}\n"
            f"\n____________________________________________________________"
            f"  {overall}\n"
        )


@dataclass(frozen=True)
class _CheckContext:
    """Resolved configuration used by all checks. Built once by _build_context."""

    key_path: str
    timeout: int
    ip_usb: str
    ip_wifi: str | None


# ============================================================
# SSH SESSION
# ============================================================


@contextmanager
def _open_ssh_session(ip: str, key_path: str, timeout: int):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=ip,
            username="root",
            key_filename=key_path,
            timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        yield client
    finally:
        client.close()


# ============================================================
# INTERNAL HELPERS
# ============================================================


def _check_binary(name: str, args: list[str], not_found_detail: str) -> CheckItem:
    """
    Checks whether a CLI binary is available in the PATH.

    Args:
        name:             Name displayed in the CheckItem (e.g. "Pandoc").
        args:             Check command (e.g. ["pandoc", "--version"]).
        not_found_detail: Message displayed if the binary is not in the PATH.

    Returns:
        CheckItem - never raises.
    """
    binary = args[0]
    if shutil.which(binary) is None:
        return CheckItem(name=name, status=False, detail=not_found_detail)
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return CheckItem(
                name=name,
                status=False,
                detail=f"found but returned non-zero exit code {result.returncode}",
            )
        version_line = result.stdout.splitlines()[0] if result.stdout else "unknown version"
        return CheckItem(name=name, status=True, detail=version_line)
    except subprocess.TimeoutExpired:
        return CheckItem(
            name=name,
            status=False,
            detail=f"found but timed out on {args[-1]}",
        )


def _check_os() -> CheckItem:
    """Detect and report the current operating system. Never raises."""
    return CheckItem(
        name="OS detected",
        status=True,
        detail=f"{platform.system()} ({platform.version()})",
    )


def check_pandoc() -> CheckItem:
    """Check that Pandoc is installed and included in the PATH. Never raises."""
    return _check_binary(
        "Pandoc",
        ["pandoc", "--version"],
        "not found in PATH - install from https://pandoc.org/installing.html and add to PATH",
    )


def check_typst() -> CheckItem:
    """Check that Typst is installed and accessible in the PATH. Never raises an exception."""
    return _check_binary(
        "Typst",
        ["typst", "--version"],
        "not found in PATH - install Typst (https://typst.app) and add to PATH",
    )


def _check_ssh(label: str, ip: str, key_path: str, timeout: int) -> CheckItem:
    """
    Attempt an SSH connection to the reMarkable using a private key.

    Parameters
    ----------
    label : str
        Display name for this check (e.g. 'SSH USB connection').
    ip : str
        IP address of the reMarkable.
    key_path : str
        Path to the private SSH key (no passphrase).
    timeout : int
        Connection timeout in seconds.

    Returns
    -------
    CheckItem
        Result of the connection attempt - never raises.
    """
    try:
        with _open_ssh_session(ip, key_path, timeout):
            return CheckItem(name=label, status=True, detail=f"connected to root@{ip}")
    except FileNotFoundError:
        return CheckItem(name=label, status=False, detail=f"SSH key not found: {key_path}")
    except paramiko.AuthenticationException:
        return CheckItem(
            name=label,
            status=False,
            detail=(
                f"authentication failed for root@{ip}"
                " - check that the public key is deployed on the tablet"
            ),
        )
    except (paramiko.SSHException, OSError, TimeoutError) as exc:
        return CheckItem(name=label, status=False, detail=f"connection failed to {ip}: {exc}")


def _check_firmware(ip: str, key_path: str, timeout: int) -> CheckItem:
    """
    Read the firmware version from the reMarkable over SSH.

    Parameters
    ----------
    ip : str
        IP address of the reMarkable.
    key_path : str
        Path to the private SSH key.
    timeout : int
        Connection timeout in seconds.

    Returns
    -------
    CheckItem
        Firmware version string, or failure detail - never raises.
    """
    try:
        with _open_ssh_session(ip, key_path, timeout) as client:
            _, stdout, _ = client.exec_command("cat /etc/version")
            version = stdout.read().decode().strip()
            detail = version if version else "connected but version file empty"
            return CheckItem(name="reMarkable firmware", status=True, detail=detail)
    except (paramiko.SSHException, OSError, TimeoutError) as exc:
        return CheckItem(
            name="reMarkable firmware",
            status=False,
            detail=f"could not read firmware version: {exc}",
        )


# ============================================================
# ORCHESTRATION
# ============================================================


def _build_context(config: dict) -> _CheckContext:
    """
    Extracts and validates the configuration. Can be tested independently of run_check.

    Parameters
    ----------
    config : dict
        Parsed content of config.yaml.

    Returns
    -------
    _CheckContext
        Resolved values ready for use by all checks.
    """
    return _CheckContext(
        key_path=os.path.expanduser(config.get("ssh_key_path", "~/.ssh/id_rsa_remarkable")),
        timeout=int(config.get("ssh_timeout", 5)),
        ip_usb=config.get("remarkable_ip_usb", "10.11.99.1"),
        ip_wifi=config.get("remarkable_ip_wifi") or None,
    )


def _build_checklist(ctx: _CheckContext) -> list[Callable[[], CheckItem]]:
    """
    Constructs the ordered list of checks to be executed.

    The firmware -> SSH dependency is explicitly resolved here:
    _check_firmware is only added if an SSH connection is available,
    and receives the corresponding IP address as a bound parameter.

    .. note::
        SSH checks (USB and WiFi) are executed **eagerly** during this call,
        not lazily during _execute(). Their results are cached in closures
        and replayed when _execute() calls the returned callables.
        This design avoids opening two SSH connections to the same host
        and allows firmware_ip to be resolved before the checklist is returned.

    Parameters
    ----------
    ctx: _CheckContext
        Resolved configuration.

    Returns
    -------
    list[Callable[[], CheckItem]]
        Ordered list of zero-argument callables, ready for _execute.
        Order: OS, Pandoc, SSH USB (cached), SSH WiFi (cached), Firmware, Typst.
    """

    def ssh_usb() -> CheckItem:
        return _check_ssh("SSH USB connection", ctx.ip_usb, ctx.key_path, ctx.timeout)

    def ssh_wifi() -> CheckItem:
        if not ctx.ip_wifi:
            return CheckItem(
                name="SSH WiFi connection",
                status=True,
                detail="skipped - no WiFi IP configured",
            )
        return _check_ssh("SSH WiFi connection", ctx.ip_wifi, ctx.key_path, ctx.timeout)

    # Explicit resolution of the firmware dependency -> SSH
    # The checks are called once here to resolve firmware_ip;
    # their results are cached and returned by the closures below.
    _ssh_usb_result = ssh_usb()
    _ssh_wifi_result = ssh_wifi()

    if _ssh_usb_result.status:
        firmware_ip = ctx.ip_usb
    elif _ssh_wifi_result.status:
        firmware_ip = ctx.ip_wifi
    else:
        firmware_ip = None

    def ssh_usb_cached() -> CheckItem:
        return _ssh_usb_result

    def ssh_wifi_cached() -> CheckItem:
        return _ssh_wifi_result

    def firmware_check() -> CheckItem:
        if firmware_ip is None:
            return CheckItem(
                name="reMarkable firmware",
                status=False,
                detail="skipped - no SSH connection available",
            )
        return _check_firmware(firmware_ip, ctx.key_path, ctx.timeout)

    return [
        _check_os,  # Step 1 - OS
        check_pandoc,  # Step 2 - Pandoc
        ssh_usb_cached,  # Step 3 - SSH USB
        ssh_wifi_cached,  # Step 4 - SSH WiFi
        firmware_check,  # Step 5 - Firmware
        check_typst,  # Step 6 - Typst
    ]


def _execute(checks: list[Callable[[], CheckItem]]) -> CheckReport:
    """
    Executes a list of checks sequentially and aggregates the results.

    Each check is independent - any unexpected exception is caught
    and converted into a failed CheckItem so as not to interrupt subsequent checks.

    Parameters
    ----------
    checks: list[Callable[[], CheckItem]]
        Ordered list of zero-argument callables.

    Returns
    -------
    CheckReport
        Aggregated results.
    """
    report = CheckReport()
    for check in checks:
        try:
            report.items.append(check())
        except Exception as exc:
            report.items.append(
                CheckItem(name=check.__name__, status=False, detail=f"unexpected error: {exc}")
            )
    return report


# ============================================================
# PUBLIC API
# ============================================================


def run_check(config: dict) -> CheckReport:
    """
    Run all installation checks and return an aggregated report.

    Checks are independent - a failure in one does not abort the others.
    SSH checks are skipped if the corresponding IP is absent or empty in config.

    Parameters
    ----------
    config : dict
        Parsed content of config.yaml. Expected keys:
        - remarkable_ip_usb (str)
        - remarkable_ip_wifi (str, optional - empty string to skip)
        - ssh_key_path (str)
        - ssh_timeout (int)

    Returns
    -------
    CheckReport
        Contains one CheckItem per verification. Inspect .all_ok to decide
        whether the pipeline can proceed.
    """
    ctx = _build_context(config)
    checks = _build_checklist(ctx)
    return _execute(checks)
