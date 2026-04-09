# Roadmap

> This document tracks planned and completed features across the project lifecycle.
>
> Updated with each new ADR creation or status change.
> Feature refs [XXXX] correspond to files in `docs/ADRs/`.

---

## Status Legend

| Symbol | Meaning              |
|--------|----------------------|
| ✅     | Done                 |
| 🔄     | In progress          |
| 📋     | Planned              |
| 💡     | Idea / not committed |

---

## Phase 0 - Project Foundation

| Ref | Feature | Status |
|-----|---------|--------|
| [0000](./ADRs/0000_InitializeProject.md) | Initialize project structure | ✅ |

---

## Phase 1 - Setup & Vault Scanning

| Ref | Feature | Status |
|-----|---------|--------|
| [0001](./ADRs/0001_SetupCheck.md) | Setup check - hardware and software installation | ✅ |
| [0002](./ADRs/0002_VaultScanner.md) | Vault scanner - Obsidian folder tree and wikilink resolution | 🔄 |

---

## Phase 2 - Core Pipeline (MVP)

| Ref | Feature | Status |
|-----|---------|--------|
| [0003] | Markdown to PDF conversion | 📋 |
| [0004] | Incremental sync engine - hash tracking and annotation protection | 📋 |
| [0005] | SSH push to reMarkable - upload PDF with xochitl metadata | 📋 |

---

## Phase 3 - Reverse Sync & CLI

| Ref | Feature | Status |
|-----|---------|--------|
| [0006] | Pull annotated notebooks from reMarkable to PC vault | 📋 |
| [0007] | CLI entry point - `--check`, `--push`, `--pull`, `--all` flags | 📋 |

---

## Phase 4 - Extensions

| Ref | Feature | Status |
|-----|---------|--------|
| [XXXX] | Emoji support in PDF - HTML/CSS pipeline via WeasyPrint or Chromium headless | 💡 |
| [XXXX] | Enriched wikilink resolution - clickable links in generated PDF | 💡 |
| [XXXX] | Watch mode - automatic sync on vault file change via `watchdog` | 💡 |
| [XXXX] | Excalidraw export from reMarkable annotations | 💡 |

---

[<-- Validation Plan](./03_Validation_Plan.md) · [Software Architecture -->](./01_Software_Architecture.md)