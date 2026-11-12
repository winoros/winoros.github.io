# winoros.github.io

Personal site & technical reports for **Yiding Cui** ([@winoros](https://github.com/winoros)).

- **Live site**: <https://winoros.github.io/> (`?lang=zh` / `?lang=en`)
- **Reports**:
  - [TiDB Optimizer Open Issues: Triage, Severity & Fix Difficulty Report](https://winoros.github.io/reports/tidb-optimizer-issues/) ([中文](https://winoros.github.io/reports/tidb-optimizer-issues/?lang=zh) · [English](https://winoros.github.io/reports/tidb-optimizer-issues/?lang=en))

## Structured i18n Layout

- `i18n/i18n.js`: Shared zero-dependency i18n engine (locale detection via `?lang=`, `localStorage`, and `navigator.languages`; declarative `data-i18n*` DOM bindings; reactive `onChange` subscriptions).
- `i18n/{zh-CN,en}.js`: Site-level & homepage locale dictionaries with 1:1 key parity.
- `reports/tidb-optimizer-issues/i18n/{zh-CN,en}.js`: Report-specific locale dictionaries (UI controls, rubric, and canonical enum labels).
- `reports/tidb-optimizer-issues/data.json` (`schema_version: 2`): Language-neutral structured dataset using canonical enum IDs (`cat`, `severity`, `subsystem`) and localized `note` maps (`{"zh-CN": "...", "en": "..."}`).

## Incremental Triage Sync (`scripts/sync_tidb_optimizer_triage.py`)

Requires an authenticated GitHub CLI (`gh auth status`). By default, runs a **Dual-Stream $O(\Delta)$ incremental refresh** starting from `prev_snapshot_utc - 15m`:

1. **Issue stream** (`repo:pingcap/tidb is:issue updated:>=T_since`): refreshes closed/relabeled/updated tracked issues and discovers newly opened or newly labeled candidate issues in one query.
2. **PR reverse-index stream** (`is:pr updated:>=T_since` across TiDB kernel repositories): refreshes state/draft/title changes on already-linked PRs and discovers newly opened/edited PRs referencing tracked issues even when GitHub does not bump `issue.updatedAt`.

```bash
# 1. Dry-run preview (prints delta & priority matrix; writes pending new candidates if any)
python3 scripts/sync_tidb_optimizer_triage.py --dry-run

# 2. Daily incremental sync (updates data.json, data.js, and homepage card date)
python3 scripts/sync_tidb_optimizer_triage.py

# 3. Apply triage decisions for newly discovered candidates & export standalone HTML
python3 scripts/sync_tidb_optimizer_triage.py \
  --decisions /tmp/decisions.json \
  --export-html /tmp/tidb_optimizer_issues_report.html

# 4. Force full batched verification across all tracked issues
python3 scripts/sync_tidb_optimizer_triage.py --full
```
