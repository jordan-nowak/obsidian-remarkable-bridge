# obsidian-remarkable-bridge

![CI](https://github.com/jordan-nowak/obsidian-remarkable-bridge/actions/workflows/ci.yml/badge.svg)
[![Coverage (main)](https://codecov.io/gh/jordan-nowak/obsidian-remarkable-bridge/branch/main/graph/badge.svg?label=coverage%20main)](https://codecov.io/gh/jordan-nowak/obsidian-remarkable-bridge/branch/main)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A Python project that synchronizes Obsidian Markdown notes to a ReMarkable 2 as PDF files via SSH. For this, it converts `.md` files into PDFs optimized for e-ink tablets using Pandoc, and manages the folder structure via a `.metadata` JSON file.

---

## Project Objective
Synchronize a structured Obsidian vault (PC) with a reMarkable 2 tablet, without relying on the reMarkable cloud subscription.

**In scope:** PC -> rM push (markdown to PDF), rM -> PC pull (annotated notebooks), annotation protection (no overwrite of annotated PDFs).

**Out of scope:** rM1 / RMPP / RMPPM compatibility, automatic background sync, annotation-to-markdown conversion.

---

## Documentation

| Document                                                    | Description                                   |
| ----------------------------------------------------------- | --------------------------------------------- |
| [Roadmap](./docs/Roadmap.md)                                | Planned and completed features                |
| [Software Architecture](./docs/01_Software_Architecture.md) | Package structure and module responsibilities |
| [Decision Records](./docs/ADRs/)                            | One ADR per feature                           |

---

## Installation
To install and configure the project locally (here for Windows), you can follow these commands:
```bash
git clone https://github.com/jordan-nowak/obsidian-remarkable-bridge.git
cd obsidian-remarkable-bridge

py -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

py -m pip install --upgrade pip
py -m pip install -e .[dev]
```

**Prerequisites:**
- Python 3.11+
- [Pandoc](https://pandoc.org/installing.html) - must be available in PATH
- SSH access to reMarkable 2 (USB or WiFi) - see [SSH Setup](./docs/setup_ssh.md)

---

## Configuration
Edit `config.yaml` before first use:
```yaml
vault_path: "C:/Users/<user>/obsidian-vault"   # Windows
# vault_path: "/home/<user>/obsidian-vault"    # Linux / macOS

remarkable_ip_usb: "10.11.99.1"
ssh_key_path: "~/.ssh/id_rsa_remarkable"
ssh_timeout: 5
target_folder: "obsidian-notes"
```

---

## Usage
```bash
# Verify the installation
python scripts/sync.py --check

# Push vault to reMarkable
python scripts/sync.py --push

# Pull notebook annoted
python scripts/sync.py --pull

# Check, push and pull with one command
python scripts/sync.py --all
```

---

## Development Contribution
If you develop, please create a new branch (`feature`, `chore`, `fix`, `doc`, `test`...) on the `develop` branch, following these steps:
```bash
git checkout develop
git pull origin develop
git checkout -b feature/xxxx-SimpleTitleToDescribeTheFeature
```

Notes: 
> - `xxxx` represents the incremental feature number.
> - A Pull Request template is provided to guide contributions. Please fill it in carefully.
> - Ensuring all tests pass and coverage remains ≥ 90% before requesting a review.
> - Each feature should be accompanied by its ADR in `docs/ADRs/` folder and any relevant update to the architecture, design, or validation documents

---

## Run Tests
Don't forget to develop tests for each development made. It is necessary to run all tests with the following command:
```bash
pytest
```

## License
The license that applies to the whole package content is MIT. Please look at the [LICENSE](./LICENSE) file at the root of this repository for more details.

## Maintainer
- Jordan NOWAK (JNo)