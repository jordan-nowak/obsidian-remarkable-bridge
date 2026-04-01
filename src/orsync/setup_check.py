"""
Installation verification for obsidian-remarkable-bridge.

Checks that all required dependencies (Pandoc, SSH connection to reMarkable)
are available before the sync pipeline is started.

Conventions:
- Each check is independent - a failed check does not abort the others.
- The caller inspects CheckReport.all_ok to decide whether to proceed.
- SSH checks use paramiko with a short configurable timeout.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field

import paramiko

# ============================================================
# DATA CLASS
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
        """
        Return a formatted report.

        Returns
        -------
        str
            String representation showing result of the report.
        """
        items_repr = ""
        for item in self.items:
            items_repr += "\n" + str(item)
        overall = "All checks passed ✅" if self.all_ok else "Some checks failed ❌"
        return (
            f"\n__ Installation Check ______________________________________"
            f"  {items_repr}\n"
            f"\n____________________________________________________________"
            f"  {overall}\n"
        )


# ============================================================
# INTERNAL CHECK HELPERS
# ============================================================


def _check_os() -> CheckItem:
    """
    Detect and report the current operating system.

    Returns
    -------
    CheckItem
        Result of the verification - never raises.
    """
    os_name = platform.system()
    version = platform.version()
    return CheckItem(
        name="OS detected",
        status=True,
        detail=f"{os_name} ({version})",
    )


def _check_pandoc() -> CheckItem:
    """
    Verify that Pandoc is installed and reachable in PATH.

    Returns
    -------
    CheckItem
        Result of the verification - never raises.
    """
    if shutil.which("pandoc") is None:
        return CheckItem(
            name="Pandoc",
            status=False,
            detail="not found in PATH - install from https://pandoc.org/installing.html and add to PATH",
        )

    try:
        result = subprocess.run(
            ["pandoc", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return CheckItem(
                name="Pandoc",
                status=False,
                detail=f"found but returned non-zero exit code {result.returncode}",
            )
        version_line = result.stdout.splitlines()[0] if result.stdout else "unknown version"
        return CheckItem(name="Pandoc", status=True, detail=version_line)

    except subprocess.TimeoutExpired:
        return CheckItem(
            name="Pandoc",
            status=False,
            detail="found but timed out on --version",
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
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # [TODO] c'est quoi ?

    try:
        client.connect(
            hostname=ip,
            username="root",
            key_filename=key_path,
            timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        return CheckItem(name=label, status=True, detail=f"connected to root@{ip}")

    except FileNotFoundError:
        return CheckItem(
            name=label,
            status=False,
            detail=f"SSH key not found: {key_path}",
        )
    except paramiko.AuthenticationException:
        return CheckItem(
            name=label,
            status=False,
            detail=f"authentication failed for root@{ip} - check that the public key is deployed on the tablet",
        )
    except (paramiko.SSHException, OSError, TimeoutError) as exc:
        return CheckItem(
            name=label,
            status=False,
            detail=f"connection failed to {ip}: {exc}",
        )
    finally:
        client.close()


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
    finally:
        client.close()


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
    report = CheckReport()
    key_path: str = os.path.expanduser(config.get("ssh_key_path", "~/.ssh/id_rsa_remarkable"))
    timeout: int = int(config.get("ssh_timeout", 5))
    ip_usb: str = config.get("remarkable_ip_usb", "10.11.99.1")
    ip_wifi: str | None = config.get("remarkable_ip_wifi") or None

    # Step 1 - OS
    report.items.append(_check_os())

    # Step 2 - Pandoc
    report.items.append(_check_pandoc())

    # Step 3 - SSH USB
    ssh_usb = _check_ssh("SSH USB connection", ip_usb, key_path, timeout)
    report.items.append(ssh_usb)

    # Step 4 - SSH WiFi (skipped if no IP configured)
    if ip_wifi:
        ssh_wifi = _check_ssh("SSH WiFi connection", ip_wifi, key_path, timeout)
        report.items.append(ssh_wifi)
    else:
        report.items.append(
            CheckItem(
                name="SSH WiFi connection", status=True, detail="skipped - no WiFi IP configured"
            )
        )

    # Step 5 - Firmware (from whichever SSH succeeded first)
    if ssh_usb.status:
        report.items.append(_check_firmware(ip_usb, key_path, timeout))
    elif ip_wifi and ssh_wifi and ssh_wifi.status:
        report.items.append(_check_firmware(ip_wifi, key_path, timeout))
    else:
        report.items.append(
            CheckItem(
                name="reMarkable firmware",
                status=False,
                detail="skipped - no SSH connection available",
            )
        )

    return report
