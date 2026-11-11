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
