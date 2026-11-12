#!/usr/bin/env python3
"""Incremental & full sync tool for the TiDB Optimizer Open Issues triage dataset.

Default mode uses a Dual-Stream O(delta) incremental strategy via `gh api graphql`:
  1. Issue stream (`repo:pingcap/tidb is:issue updated:>=T_since`, including closed):
     - Detects state/label/title/assignee/comment updates on existing tracked issues.
     - Discovers newly opened or newly labeled candidate issues in a single query.
  2. PR reverse-index stream (`is:pr updated:>=T_since` across TiDB kernel repos):
     - Captures state/draft/title updates and unlinks on already-linked PRs even when
       GitHub does NOT advance `issue.updatedAt`.
     - Captures newly opened/edited PRs referencing tracked issues via closing refs,
       PR title/body, recent commits, or PR comments.

Automatically falls back to `--full` batched verification if the time gap exceeds
`--max-incremental-days` (default: 14) or if GitHub Search approaches its 1,000-hit cap.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

UTC = dt.timezone.utc
UTC8 = dt.timezone(dt.timedelta(hours=8))

KERNEL_REPOS = (
    "pingcap/tidb",
    "pingcap/tiflash",
    "tikv/tikv",
    "pingcap/parser",
    "tikv/pd",
    "pingcap/tiflow",
    "pingcap/ticdc",
)
KERNEL_REPO_SET = set(KERNEL_REPOS)

NON_PLANNER_SIGS = {
    "sig/execution",
    "sig/transaction",
    "sig/sql-infra",
    "sig/migrate",
    "sig/diagnosis",
}

# Components that are unambiguously outside the SQL optimizer when `sig/planner` is absent.
NON_OPT_COMPONENTS_WITHOUT_PLANNER_SIG = {
    "component/br",
    "component/lightning",
    "component/dumpling",
    "component/ddl",
    "component/privilege",
    "component/cdc",
    "component/ticdc",
}

# Historical PR links mentioned only in plain comments without a GitHub CrossReferencedEvent.
STATIC_EXTRA_PR_MAP: dict[int, list[dict[str, Any]]] = {
    65653: [
        {
            "num": 67129,
            "repo": "pingcap/tidb",
            "label": "#67129",
            "url": "https://github.com/pingcap/tidb/pull/67129",
            "state": "MERGED",
            "title": "planner: replace outer-join null-reject evaluation with structural proof | tidb-test=pr/2724",
            "is_cherry_pick": False,
            "updated_at": "",
        }
    ],
}

DIFF_RANK = {
    "EASY": 1,
    "MEDIUM": 2,
    "HARD": 3,
    "ENHANCEMENT": 0,
    "FILTER_RANDOM_FUZZ": 0,
    "FILTER_AI_OBSCURE": 0,
    "FILTER_NON_OPT_OR_FIXED": 0,
}

SEV_RANK = {
    "CRITICAL": 4,
    "MAJOR": 3,
    "MODERATE": 2,
    "MINOR": 1,
    "N/A": 0,
}

VALID_SUBSYSTEMS = {
    "statistics",
    "plan_cache_spm_hint",
    "logical_rewrite",
    "access_path_partition_lock",
    "cbo_cost_join_reorder",
    "name_resolution_group_by",
    "tiflash_mpp",
}

ISSUE_FRAGMENT = """
fragment IssueFields on Issue {
  number
  title
  state
  stateReason
  createdAt
  updatedAt
  closedAt
  author { login }
  assignees(first: 10) { nodes { login } }
  labels(first: 30) { nodes { name } }
  timelineItems(itemTypes: [CROSS_REFERENCED_EVENT, CONNECTED_EVENT], first: 50) {
    totalCount
    nodes {
      __typename
      ... on CrossReferencedEvent {
        source {
          __typename
          ... on PullRequest {
            number
            title
            state
            isDraft
            url
            updatedAt
            mergedAt
            repository { nameWithOwner }
          }
        }
      }
      ... on ConnectedEvent {
        subject {
          __typename
          ... on PullRequest {
            number
            title
            state
            isDraft
            url
            updatedAt
            mergedAt
            repository { nameWithOwner }
          }
        }
      }
    }
  }
}
"""

DETAIL_FRAGMENT = (
    ISSUE_FRAGMENT
    + """
fragment IssueDetailFields on Issue {
  ...IssueFields
  body
  comments(last: 15) {
    totalCount
    nodes {
      author { login }
      createdAt
      body
    }
  }
}
"""
)

SEARCH_ISSUES_GQL = """
query($q: String!, $cursor: String) {
  search(query: $q, type: ISSUE, first: 100, after: $cursor) {
    issueCount
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on Issue {
        number
        title
        state
        createdAt
        updatedAt
        labels(first: 30) { nodes { name } }
      }
    }
  }
}
"""

SEARCH_PRS_GQL = """
query($q: String!, $cursor: String) {
  search(query: $q, type: ISSUE, first: 50, after: $cursor) {
    issueCount
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on PullRequest {
        number
        title
        body
        state
        isDraft
        updatedAt
        repository { nameWithOwner }
        closingIssuesReferences(first: 20) {
          nodes {
            number
            repository { nameWithOwner }
          }
        }
        commits(last: 15) {
          nodes {
            commit {
              messageHeadline
              messageBody
            }
          }
        }
        comments(last: 10) {
          nodes {
            body
          }
        }
      }
    }
  }
}
"""

LOCAL_ISSUE_REF_RE = re.compile(r"(?<![A-Za-z0-9_/-])#(\d{4,6})\b")
CROSS_TIDB_ISSUE_REF_RE = re.compile(
    r"(?:pingcap/tidb#|github\.com/pingcap/tidb/issues/)(\d{4,6})\b", re.IGNORECASE
)
CHERRY_PICK_TITLE_RE = re.compile(r"\(#\d+\)\s*(\|.*)?$")


def parse_iso_utc(iso_str: str) -> dt.datetime:
    return dt.datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(UTC)


def format_iso_utc(ts: dt.datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_utc8_display(iso_z: str) -> str:
    return parse_iso_utc(iso_z).astimezone(UTC8).strftime("%Y-%m-%d %H:%M")


class GitHubGraphQLClient:
    def __init__(self) -> None:
        self.call_count = 0

    def query(self, gql: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        cmd = ["gh", "api", "graphql", "-f", f"query={gql}"]
        for k, v in (variables or {}).items():
            if v is not None:
                cmd.extend(["-f", f"{k}={v}"])
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                self.call_count += 1
                out = subprocess.check_output(cmd, stderr=subprocess.PIPE)
                payload = json.loads(out)
                if "errors" in payload and not payload.get("data"):
                    raise RuntimeError(f"GraphQL error: {payload['errors']}")
                if "errors" in payload:
                    print(f"[warn] GraphQL partial errors: {payload['errors']}", file=sys.stderr)
                return payload
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"gh api graphql failed after 3 attempts: {last_err}") from last_err

    def search_all(self, gql: str, q: str, max_hits: int = 900) -> tuple[int, list[dict[str, Any]]]:
        nodes: list[dict[str, Any]] = []
        cursor: str | None = None
        total_count = 0
        while True:
            data = self.query(gql, {"q": q, "cursor": cursor})
            s = data["data"]["search"]
            total_count = int(s["issueCount"])
            if total_count > max_hits:
                return total_count, []
            for n in s["nodes"]:
                if n and "number" in n:
                    nodes.append(n)
            if not s["pageInfo"]["hasNextPage"]:
                break
            cursor = s["pageInfo"]["endCursor"]
        return total_count, nodes

    def fetch_issues_batch(
        self, nums: list[int], detailed: bool = True, batch_size: int | None = None
    ) -> dict[int, dict[str, Any]]:
        if not nums:
            return {}
        step = batch_size or (25 if detailed else 50)
        frag_decl = DETAIL_FRAGMENT if detailed else ISSUE_FRAGMENT
        frag_name = "IssueDetailFields" if detailed else "IssueFields"
        result: dict[int, dict[str, Any]] = {}
        ordered = sorted(set(nums), reverse=True)
        for idx in range(0, len(ordered), step):
            chunk = ordered[idx : idx + step]
            aliases = "\n    ".join(f"i{n}: issue(number: {n}) {{ ...{frag_name} }}" for n in chunk)
            gql = (
                f"{frag_decl}\n"
                f'query {{\n  repository(owner: "pingcap", name: "tidb") {{\n    {aliases}\n  }}\n}}'
            )
            repo_data = self.query(gql)["data"]["repository"]
            for n in chunk:
                item = repo_data.get(f"i{n}")
                if item:
                    result[n] = item
        return result


def matched_candidate_scopes(
    labels_list: list[str], title: str, created_at: str, *, is_existing: bool
) -> list[str]:
    lbs = set(labels_list)
    hits: list[str] = []

    if "sig/planner" in lbs and "type/bug" in lbs:
        hits.append("canonical_planner_bug")

    if (
        "sig/planner" in lbs
        and "type/bug" not in lbs
        and "type/enhancement" not in lbs
        and "type/feature-request" not in lbs
        and "type/sub-task" not in lbs
    ):
        hits.append("planner_no_type")

    for comp in ("statistics", "bindinfo", "spm", "mview"):
        if f"component/{comp}" in lbs and "type/bug" in lbs and "sig/planner" not in lbs:
            hits.append(f"comp_{comp}")

    for pl in ("cascades", "performance", "join-order"):
        if f"planner/{pl}" in lbs and "sig/planner" not in lbs:
            hits.append(f"planner_{pl}")

    non_opt_guard = not is_existing and (
        bool(lbs & NON_OPT_COMPONENTS_WITHOUT_PLANNER_SIG)
        or "flaky-test" in lbs
        or title.lower().startswith(("br:", "lightning:", "dumpling:", "flaky test:"))
    )

    if (
        created_at >= "2026-01-01"
        and "type/bug" in lbs
        and "sig/planner" not in lbs
        and not (lbs & NON_PLANNER_SIGS)
        and not non_opt_guard
    ):
        hits.append("untriaged_2026_bug")

    if (
        created_at >= "2026-01-01"
        and not (lbs & {"sig/planner", "type/bug", "type/enhancement", "type/feature-request"})
        and not (lbs & NON_PLANNER_SIGS)
        and not non_opt_guard
        and re.search(r"planner|optimizer|statistics|binding|plan", title, re.IGNORECASE)
    ):
        hits.append("extra_title_no_type")

    return hits


def extract_tidb_issue_refs_from_pr(pr_node: dict[str, Any]) -> set[int]:
    refs: set[int] = set()
    repo = pr_node["repository"]["nameWithOwner"]

    for ci in (pr_node.get("closingIssuesReferences", {}).get("nodes") or []):
        if ci and ci.get("repository", {}).get("nameWithOwner") == "pingcap/tidb":
            refs.add(int(ci["number"]))

    texts: list[str] = [pr_node.get("title") or "", pr_node.get("body") or ""]
    for cm_wrap in (pr_node.get("commits", {}).get("nodes") or []):
        cm = (cm_wrap or {}).get("commit") or {}
        texts.append(cm.get("messageHeadline") or "")
        texts.append(cm.get("messageBody") or "")
    for cmt in (pr_node.get("comments", {}).get("nodes") or []):
        if cmt:
            texts.append(cmt.get("body") or "")

    combined = "\n".join(texts)
    for m in CROSS_TIDB_ISSUE_REF_RE.finditer(combined):
        refs.add(int(m.group(1)))
    if repo == "pingcap/tidb":
        for m in LOCAL_ISSUE_REF_RE.finditer(combined):
            refs.add(int(m.group(1)))
    return refs


def extract_prs_from_issue(iss_num: int, live_item: dict[str, Any]) -> list[dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}
    for node in (live_item.get("timelineItems", {}).get("nodes") or []):
        if not node:
            continue
        pr = node.get("source") or node.get("subject")
        if not pr or pr.get("__typename") != "PullRequest":
            continue
        repo = pr["repository"]["nameWithOwner"]
        if repo not in KERNEL_REPO_SET:
            continue
        url = pr["url"]
        raw_state = pr["state"]
        state = "DRAFT" if (raw_state == "OPEN" and pr.get("isDraft")) else raw_state
        title = pr["title"]
        is_cp = (
            bool(CHERRY_PICK_TITLE_RE.search(title))
            or title.lower().startswith("[cherry-pick]")
            or "automated cherry pick" in title.lower()
        )
        short_repo = "" if repo == "pingcap/tidb" else repo.split("/")[1]
        label = f"#{pr['number']}" if not short_repo else f"{short_repo}#{pr['number']}"
        by_url[url] = {
            "num": int(pr["number"]),
            "repo": repo,
            "label": label,
            "url": url,
            "state": state,
            "title": title,
            "is_cherry_pick": is_cp,
            "updated_at": pr.get("updatedAt") or "",
        }

    for extra_pr in STATIC_EXTRA_PR_MAP.get(iss_num, []):
        if extra_pr["url"] not in by_url:
            by_url[extra_pr["url"]] = extra_pr

    def sort_key(p: dict[str, Any]) -> tuple[int, int]:
        st_rank = {
            ("OPEN", False): 0,
            ("DRAFT", False): 1,
            ("MERGED", False): 2,
            ("OPEN", True): 3,
            ("DRAFT", True): 4,
            ("MERGED", True): 5,
            ("CLOSED", False): 6,
            ("CLOSED", True): 7,
        }.get((p["state"], p.get("is_cherry_pick", False)), 8)
        return (st_rank, -int(p["num"]))

    return sorted(by_url.values(), key=sort_key)


def build_record(
    n: int,
    live_it: dict[str, Any],
    cat: str,
    sev: str,
    subsys: str,
    is_borderline: bool,
    note: dict[str, str] | None,
) -> dict[str, Any]:
    if cat not in DIFF_RANK:
        raise ValueError(f"Invalid category '{cat}' for #{n}")
    if sev not in SEV_RANK:
        raise ValueError(f"Invalid severity '{sev}' for #{n}")
    if subsys not in VALID_SUBSYSTEMS:
        raise ValueError(f"Invalid subsystem '{subsys}' for #{n}")

    labels = [l["name"] for l in (live_it.get("labels", {}).get("nodes") or []) if l]
    gh_sevs = [l.split("/")[1] for l in labels if l.startswith("severity/")]
    gh_sev = gh_sevs[0] if gh_sevs else "unlabeled"

    prs = extract_prs_from_issue(n, live_it)
    has_open_pr = any(p["state"] in ("OPEN", "DRAFT") and not p["is_cherry_pick"] for p in prs)
    has_any_open_pr = any(p["state"] in ("OPEN", "DRAFT") for p in prs)
    has_merged_pr = any(p["state"] == "MERGED" for p in prs)

    return {
        "number": n,
        "title": live_it["title"],
        "author": (live_it.get("author") or {}).get("login", "ghost"),
        "assignees": [a["login"] for a in (live_it.get("assignees", {}).get("nodes") or []) if a],
        "created": live_it["createdAt"][:10],
        "created_at": live_it["createdAt"],
        "updated_at": live_it["updatedAt"],
        "updated_display": to_utc8_display(live_it["updatedAt"]),
        "labels": labels,
        "is_canonical": ("sig/planner" in labels and "type/bug" in labels),
        "is_customer": ("report/customer" in labels),
        "is_borderline_kept": bool(is_borderline),
        "cat": cat,
        "diff_rank": DIFF_RANK[cat],
        "severity": sev,
        "sev_rank": SEV_RANK[sev],
        "gh_severity": gh_sev,
        "subsystem": subsys,
        "note": {"zh-CN": note["zh-CN"], "en": note["en"]} if note else None,
        "prs": prs,
        "has_pr": len(prs) > 0,
        "has_open_pr": has_open_pr,
        "has_any_open_pr": has_any_open_pr,
        "has_merged_pr": has_merged_pr,
    }


def export_standalone_html(site_root: Path, js_payload: str, out_path: Path) -> None:
    report_dir = site_root / "reports" / "tidb-optimizer-issues"
    raw_html = (report_dir / "index.html").read_text(encoding="utf-8")
    art_html = raw_html.replace(
        '<a href="../../" data-keep-lang data-i18n="common.backHome">',
        '<a href="https://winoros.github.io/" target="_blank" rel="noopener" data-i18n="common.backHome">',
    ).replace(
        '<a href="./data.json" target="_blank" rel="noopener" data-i18n="report.nav.dataJson">',
        '<a href="https://winoros.github.io/reports/tidb-optimizer-issues/data.json" target="_blank" rel="noopener" data-i18n="report.nav.dataJson">',
    )
    inline_scripts = "\n".join(
        [
            "<script>",
            (site_root / "i18n" / "i18n.js").read_text(encoding="utf-8"),
            (site_root / "i18n" / "zh-CN.js").read_text(encoding="utf-8"),
            (site_root / "i18n" / "en.js").read_text(encoding="utf-8"),
            (report_dir / "i18n" / "zh-CN.js").read_text(encoding="utf-8"),
            (report_dir / "i18n" / "en.js").read_text(encoding="utf-8"),
            "window.REPORT_DATASET = " + js_payload + ";",
            "</script>",
        ]
    )
    target_block = "\n".join(
        [
            '<script src="../../i18n/i18n.js"></script>',
            '<script src="../../i18n/zh-CN.js"></script>',
            '<script src="../../i18n/en.js"></script>',
            '<script src="./i18n/zh-CN.js"></script>',
            '<script src="./i18n/en.js"></script>',
            '<script src="./data.js"></script>',
        ]
    )
    if target_block not in art_html:
        raise RuntimeError("Expected external <script> block not found in reports/tidb-optimizer-issues/index.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(art_html.replace(target_block, inline_scripts), encoding="utf-8")


def write_pending_bundle(pending_path: Path, pending_items: list[tuple[int, list[str], dict[str, Any]]]) -> None:
    issues_detail = []
    template_new: dict[str, Any] = {}
    for num, scopes, it in pending_items:
        labels = [l["name"] for l in (it.get("labels", {}).get("nodes") or []) if l]
        prs = extract_prs_from_issue(num, it)
        comments = [
            {
                "author": (c.get("author") or {}).get("login", "ghost"),
                "created_at": c.get("createdAt"),
                "body": c.get("body") or "",
            }
            for c in (it.get("comments", {}).get("nodes") or [])
            if c
        ]
        issues_detail.append(
            {
                "number": num,
                "url": f"https://github.com/pingcap/tidb/issues/{num}",
                "title": it["title"],
                "author": (it.get("author") or {}).get("login", "ghost"),
                "created_at": it["createdAt"],
                "updated_at": it["updatedAt"],
                "labels": labels,
                "matched_scopes": scopes,
                "prs": prs,
                "body": it.get("body") or "",
                "recent_comments": comments,
            }
        )
        template_new[str(num)] = {
            "cat": "MEDIUM",
            "severity": "MAJOR",
            "subsystem": "logical_rewrite",
            "is_borderline_kept": False,
            "note": {
                "zh-CN": "TODO: 填写中文根因与影响简述",
                "en": "TODO: Fill in concise English root-cause & impact note",
            },
        }

    bundle = {
        "instructions": (
            "Copy `decisions_template` to a JSON file, fill in triage judgments for `new_issues` "
            "(or move non-optimizer untriaged issues into `exclude_issues` with a short reason), "
            "and re-run with `--decisions <file.json>`."
        ),
        "valid_enums": {
            "cat": list(DIFF_RANK.keys()),
            "severity": list(SEV_RANK.keys()),
            "subsystem": sorted(VALID_SUBSYSTEMS),
        },
        "decisions_template": {
            "new_issues": template_new,
            "exclude_issues": {},
            "overrides": {},
            "closed_reasons": {},
            "graduated_reasons": {},
        },
        "pending_candidates": issues_detail,
    }
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_homepage_card_date(index_html_path: Path, date_str: str) -> bool:
    if not index_html_path.exists():
        return False
    raw = index_html_path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(<a\s+class="card"\s+href="\./reports/tidb-optimizer-issues/"[\s\S]*?<span\s+class="card-date">)\d{4}-\d{2}-\d{2}(</span>)',
        rf"\g<1>{date_str}\g<2>",
        raw,
        count=1,
    )
    if count > 0 and updated != raw:
        index_html_path.write_text(updated, encoding="utf-8")
        return True
    return False


def print_summary(
    mode_used: str,
    gql_calls: int,
    prev_dataset: dict[str, Any],
    dataset: dict[str, Any],
    pr_changed_nums: list[int],
    meta_changed_nums: list[int],
) -> None:
    prev_meta = prev_dataset["sync_meta"]
    sync_meta = dataset["sync_meta"]
    records = dataset["records"]
    delta = sync_meta["delta_since_prev_snapshot"]

    c_cat = Counter(r["cat"] for r in records)
    c_can = Counter(r["cat"] for r in records if r["is_canonical"])
    real = [r for r in records if r["cat"] in ("EASY", "MEDIUM", "HARD")]

    print(f"=== SYNC SUMMARY ({mode_used.upper()} MODE · {gql_calls} GraphQL calls) ===")
    print(f"  Prev Snapshot : {prev_meta.get('snapshot_utc8')} ({prev_meta.get('snapshot_utc')})")
    print(f"  New Snapshot  : {sync_meta['snapshot_utc8']} ({sync_meta['snapshot_utc']})")
    print(f"  Max Updated   : {sync_meta['max_issue_updated_utc8']} ({sync_meta['max_issue_updated_utc']})")
    print(f"  Closed Removed: {[x['number'] for x in delta['closed_issues_removed']]}")
    print(f"  Graduated Out : {[x['number'] for x in delta.get('relabeled_graduated_removed', [])]}")
    print(f"  New Added     : {[x['number'] for x in delta['new_open_candidates_added']]}")
    print(f"  PR-Diff Issues: {pr_changed_nums}")
    print(f"  Meta-Updated  : {meta_changed_nums}")

    print(f"\n=== COUNTS ({prev_meta['total_candidates']} -> {len(records)}) ===")
    print(f"  Total Candidates    : {prev_meta['total_candidates']} -> {len(records)}")
    print(f"  Canonical Candidates: {prev_meta['canonical_candidates']} -> {sum(c_can.values())}")
    print(f"  Real Bugs           : {prev_meta['real_bugs']} -> {len(real)} (canonical: {sum(1 for r in real if r['is_canonical'])})")
    for k in dataset["enums"]["categories"]:
        prev_c = sum(1 for r in prev_dataset["records"] if r["cat"] == k)
        print(f"    {k:25s}: {prev_c:3d} -> {c_cat[k]:3d}  (canonical: {c_can[k]:3d})")

    print("\n=== REAL BUG PRIORITY MATRIX (Difficulty x Severity) ===")
    for d in ("EASY", "MEDIUM", "HARD"):
        row_items = [r for r in real if r["cat"] == d]
        cells = []
        for s in ("CRITICAL", "MAJOR", "MODERATE", "MINOR"):
            ci = [r for r in row_items if r["severity"] == s]
            in_pr = sum(1 for r in ci if r["has_open_pr"])
            cells.append(f"{s}={len(ci):2d} ({len(ci) - in_pr} open/{in_pr} PR)")
        tot_pr = sum(1 for r in row_items if r["has_open_pr"])
        print(
            f"  {d:6s}: "
            + " | ".join(cells)
            + f" || Total={len(row_items):3d} ({len(row_items) - tot_pr} open/{tot_pr} PR)"
        )
    tot_open_pr = sum(1 for r in real if r["has_open_pr"])
    print(f"  Grand Total: {len(real)} ({len(real) - tot_open_pr} unclaimed / {tot_open_pr} with active fix PR)")


def main() -> int:
    default_site_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Incrementally sync the TiDB Optimizer Open Issues triage dataset."
    )
    parser.add_argument(
        "--site-root",
        type=Path,
        default=default_site_root,
        help="Path to winoros.github.io repository root (default: parent of scripts/).",
    )
    parser.add_argument(
        "--data-json",
        type=Path,
        default=None,
        help="Override input/output data.json path (defaults to <site-root>/reports/tidb-optimizer-issues/data.json).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force full batched verification of all existing candidate issues instead of dual-stream incremental mode.",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Override incremental UTC ISO watermark (e.g. 2026-11-11T11:00:00Z).",
    )
    parser.add_argument(
        "--overlap-minutes",
        type=int,
        default=15,
        help="Safety overlap buffer subtracted from prev snapshot_utc in incremental mode (default: 15).",
    )
    parser.add_argument(
        "--max-incremental-days",
        type=int,
        default=14,
        help="Auto-fallback to --full when previous snapshot is older than N days (default: 14).",
    )
    parser.add_argument(
        "--decisions",
        type=Path,
        default=None,
        help="JSON file supplying triage decisions for new_issues, exclude_issues, and/or overrides.",
    )
    parser.add_argument(
        "--pending-file",
        type=Path,
        default=Path("/tmp/tidb_optimizer_pending_triage.json"),
        help="Where to write detailed bundle + template when untriaged new candidates are found.",
    )
    parser.add_argument(
        "--allow-pending",
        action="store_true",
        help="Write refreshed existing issues even when untriaged new candidates exist (tracks pending IDs in sync_meta).",
    )
    parser.add_argument(
        "--export-html",
        type=Path,
        default=None,
        help="Optional path to export a self-contained single-file HTML report (e.g. for Chordra artifact upload).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute delta and print summary without modifying repository files.",
    )
    args = parser.parse_args()

    site_root: Path = args.site_root.resolve()
    data_json_path: Path = (
        args.data_json.resolve()
        if args.data_json
        else (site_root / "reports" / "tidb-optimizer-issues" / "data.json")
    )
    data_js_path = data_json_path.with_suffix(".js")

    prev_dataset = json.loads(data_json_path.read_text(encoding="utf-8"))
    prev_meta = prev_dataset["sync_meta"]
    prev_by_num: dict[int, dict[str, Any]] = {int(r["number"]): r for r in prev_dataset["records"]}

    decisions: dict[str, Any] = {}
    if args.decisions:
        decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
        if "decisions_template" in decisions and "new_issues" not in decisions:
            decisions = decisions["decisions_template"]

    dec_new: dict[int, dict[str, Any]] = {
        int(k): v for k, v in (decisions.get("new_issues") or {}).items()
    }
    dec_exclude: dict[int, str] = {
        int(k): str(v) for k, v in (decisions.get("exclude_issues") or {}).items()
    }
    dec_overrides: dict[int, dict[str, Any]] = {
        int(k): v for k, v in (decisions.get("overrides") or {}).items()
    }
    dec_closed_reasons: dict[int, str] = {
        int(k): str(v) for k, v in (decisions.get("closed_reasons") or {}).items()
    }
    dec_graduated_reasons: dict[int, str] = {
        int(k): str(v) for k, v in (decisions.get("graduated_reasons") or {}).items()
    }

    persisted_excluded: set[int] = set(int(x) for x in prev_meta.get("excluded_issue_nums", []))
    persisted_excluded.update(dec_exclude.keys())
    persisted_pending: set[int] = set(int(x) for x in prev_meta.get("pending_candidate_nums", []))

    now_dt = dt.datetime.now(UTC)
    snapshot_utc = format_iso_utc(now_dt)
    prev_snap_dt = parse_iso_utc(prev_meta["snapshot_utc"])
    since_dt = (
        parse_iso_utc(args.since)
        if args.since
        else (prev_snap_dt - dt.timedelta(minutes=args.overlap_minutes))
    )
    since_iso = format_iso_utc(since_dt)

    use_full = args.full or ((now_dt - prev_snap_dt).total_seconds() > args.max_incremental_days * 86400)
    client = GitHubGraphQLClient()

    dirty_existing_nums: set[int] = set(dec_overrides.keys()) & set(prev_by_num.keys())
    discovered_scopes: dict[int, list[str]] = {}
    mode_used = "full" if use_full else "incremental"

    if not use_full:
        # Stream A: All pingcap/tidb issues updated since `since_iso` (including closed)
        issue_q = f"repo:pingcap/tidb is:issue updated:>={since_iso}"
        iss_count, iss_nodes = client.search_all(SEARCH_ISSUES_GQL, issue_q)

        # Stream B: All PRs across kernel repos updated since `since_iso`
        repo_qualifiers = " ".join(f"repo:{r}" for r in KERNEL_REPOS)
        pr_q = f"{repo_qualifiers} is:pr updated:>={since_iso}"
        pr_count, pr_nodes = client.search_all(SEARCH_PRS_GQL, pr_q)

        if iss_count > 900 or pr_count > 900:
            print(
                f"[info] Search hit count high (issues={iss_count}, prs={pr_count}); falling back to --full mode."
            )
            use_full = True
            mode_used = "full-fallback"
        else:
            for node in iss_nodes:
                num = int(node["number"])
                if num in prev_by_num:
                    dirty_existing_nums.add(num)
                elif node["state"] == "OPEN":
                    lbs = [l["name"] for l in (node.get("labels", {}).get("nodes") or []) if l]
                    # Re-admit previously excluded non-opt issues only if they later gained `sig/planner`
                    if num in persisted_excluded and "sig/planner" not in lbs:
                        continue
                    scopes = matched_candidate_scopes(
                        lbs, node["title"], node["createdAt"], is_existing=False
                    )
                    if scopes:
                        discovered_scopes[num] = scopes

            # Build reverse index `(repo, pr_num) -> set[issue_num]` from tracked records
            prev_pr_to_issues: dict[tuple[str, int], set[int]] = {}
            for iss_num, rec in prev_by_num.items():
                for p in rec.get("prs", []):
                    prev_pr_to_issues.setdefault((p["repo"], int(p["num"])), set()).add(iss_num)

            for pr_node in pr_nodes:
                key = (pr_node["repository"]["nameWithOwner"], int(pr_node["number"]))
                if key in prev_pr_to_issues:
                    dirty_existing_nums.update(prev_pr_to_issues[key])
                for ref_num in extract_tidb_issue_refs_from_pr(pr_node):
                    if ref_num in prev_by_num:
                        dirty_existing_nums.add(ref_num)

    live_existing: dict[int, dict[str, Any]] = {}
    if use_full:
        live_existing = client.fetch_issues_batch(list(prev_by_num.keys()), detailed=False)
        issue_q = f"repo:pingcap/tidb is:issue is:open updated:>={since_iso}"
        _, iss_nodes = client.search_all(SEARCH_ISSUES_GQL, issue_q, max_hits=1000)
        for node in iss_nodes:
            num = int(node["number"])
            if num not in prev_by_num:
                lbs = [l["name"] for l in (node.get("labels", {}).get("nodes") or []) if l]
                if num in persisted_excluded and "sig/planner" not in lbs:
                    continue
                scopes = matched_candidate_scopes(
                    lbs, node["title"], node["createdAt"], is_existing=False
                )
                if scopes:
                    discovered_scopes[num] = scopes
    else:
        if dirty_existing_nums:
            live_existing = client.fetch_issues_batch(list(dirty_existing_nums), detailed=True)

    # Also re-check any previously tracked pending candidates and explicit `dec_new` entries
    extra_new_to_fetch = (
        (set(discovered_scopes.keys()) | persisted_pending | set(dec_new.keys()))
        - set(prev_by_num.keys())
        - set(dec_exclude.keys())
    )
    live_new = client.fetch_issues_batch(list(extra_new_to_fetch), detailed=True)

    # Filter `live_new` to currently OPEN issues that still match scope (or are explicitly in `dec_new`)
    pending_untriaged: list[tuple[int, list[str], dict[str, Any]]] = []
    ready_new_nums: list[int] = []
    for num in sorted(live_new.keys(), reverse=True):
        it = live_new[num]
        if it["state"] != "OPEN":
            continue
        lbs = [l["name"] for l in (it.get("labels", {}).get("nodes") or []) if l]
        scopes = discovered_scopes.get(num) or matched_candidate_scopes(
            lbs, it["title"], it["createdAt"], is_existing=False
        )
        if num in dec_new:
            ready_new_nums.append(num)
        elif scopes:
            pending_untriaged.append((num, scopes, it))

    if pending_untriaged:
        write_pending_bundle(args.pending_file, pending_untriaged)
        print(
            f"\n[ACTION REQUIRED] Found {len(pending_untriaged)} untriaged new candidate issue(s): "
            f"{[x[0] for x in pending_untriaged]}"
        )
        for num, scopes, it in pending_untriaged:
            print(f"  - #{num} {scopes}: {it['title']}")
        print(f"  Wrote triage inspection bundle & template to: {args.pending_file}")
        if not args.allow_pending and not args.dry_run:
            print(
                "  Aborting write so new candidates can be triaged via `--decisions <file.json>` "
                "(or pass `--allow-pending` to refresh existing issues first)."
            )
            return 2

    records: list[dict[str, Any]] = []
    closed_removed: list[dict[str, Any]] = []
    graduated_removed: list[dict[str, Any]] = []
    pr_changed_nums: list[int] = []
    meta_changed_nums: list[int] = []

    for num in sorted(prev_by_num.keys(), reverse=True):
        prev_rec = prev_by_num[num]
        if num not in live_existing:
            records.append(prev_rec)
            continue

        live_it = live_existing[num]
        if live_it["state"] != "OPEN":
            closed_removed.append(
                {
                    "number": num,
                    "prev_cat": prev_rec["cat"],
                    "prev_severity": prev_rec["severity"],
                    "closed_at": live_it.get("closedAt"),
                    "reason": dec_closed_reasons.get(
                        num, f"Closed ({live_it.get('stateReason') or 'COMPLETED'})"
                    ),
                }
            )
            continue

        lbs = [l["name"] for l in (live_it.get("labels", {}).get("nodes") or []) if l]
        still_in_scope = bool(
            matched_candidate_scopes(lbs, live_it["title"], live_it["createdAt"], is_existing=True)
        )
        ovr = dec_overrides.get(num, {})
        if not still_in_scope and not ovr.get("force_keep"):
            graduated_removed.append(
                {
                    "number": num,
                    "prev_cat": prev_rec["cat"],
                    "reason": dec_graduated_reasons.get(
                        num, f"Graduated out of bug candidate scope (labels: {lbs})"
                    ),
                }
            )
            continue

        new_rec = build_record(
            n=num,
            live_it=live_it,
            cat=ovr.get("cat", prev_rec["cat"]),
            sev=ovr.get("severity", prev_rec["severity"]),
            subsys=ovr.get("subsystem", prev_rec["subsystem"]),
            is_borderline=ovr.get("is_borderline_kept", prev_rec["is_borderline_kept"]),
            note=ovr.get("note", prev_rec["note"]),
        )
        prev_pr_sig = [(p["repo"], p["num"], p["state"], p["is_cherry_pick"]) for p in prev_rec.get("prs", [])]
        new_pr_sig = [(p["repo"], p["num"], p["state"], p["is_cherry_pick"]) for p in new_rec["prs"]]
        if prev_pr_sig != new_pr_sig:
            pr_changed_nums.append(num)
        if (
            prev_rec["updated_at"] != new_rec["updated_at"]
            or prev_rec["labels"] != new_rec["labels"]
            or prev_rec["title"] != new_rec["title"]
        ):
            meta_changed_nums.append(num)
        records.append(new_rec)

    new_added_meta: list[dict[str, Any]] = []
    for num in ready_new_nums:
        tinfo = dec_new[num]
        live_it = live_new[num]
        note_val = tinfo.get("note")
        rec = build_record(
            n=num,
            live_it=live_it,
            cat=tinfo["cat"],
            sev=tinfo["severity"],
            subsys=tinfo["subsystem"],
            is_borderline=bool(tinfo.get("is_borderline_kept", False)),
            note=note_val,
        )
        records.append(rec)
        new_added_meta.append(
            {
                "number": num,
                "cat": tinfo["cat"],
                "severity": tinfo["severity"],
                "subsystem": tinfo["subsystem"],
                "reason": (note_val or {}).get("en") or tinfo["cat"],
            }
        )

    records.sort(key=lambda r: -int(r["number"]))
    c_can = Counter(r["cat"] for r in records if r["is_canonical"])
    real = [r for r in records if r["cat"] in ("EASY", "MEDIUM", "HARD")]
    max_upd = max(r["updated_at"] for r in records)

    sync_meta: dict[str, Any] = {
        "schema_version": 2,
        "supported_locales": ["zh-CN", "en"],
        "snapshot_utc": snapshot_utc,
        "snapshot_utc8": to_utc8_display(snapshot_utc) + " (UTC+8)",
        "max_issue_updated_utc": max_upd,
        "max_issue_updated_utc8": to_utc8_display(max_upd) + " (UTC+8)",
        "incremental_gh_search_qualifier": f"updated:>={max_upd}",
        "total_candidates": len(records),
        "canonical_candidates": sum(c_can.values()),
        "real_bugs": len(real),
        "delta_since_prev_snapshot": {
            "prev_snapshot_date": prev_meta["snapshot_utc"],
            "closed_issues_removed": closed_removed,
            "relabeled_graduated_removed": graduated_removed,
            "new_open_candidates_added": new_added_meta,
        },
    }
    if pending_untriaged:
        sync_meta["pending_candidate_nums"] = [x[0] for x in pending_untriaged]
    if persisted_excluded:
        sync_meta["excluded_issue_nums"] = sorted(persisted_excluded, reverse=True)

    dataset = {
        "sync_meta": sync_meta,
        "enums": prev_dataset["enums"],
        "records": records,
    }

    print_summary(mode_used, client.call_count, prev_dataset, dataset, pr_changed_nums, meta_changed_nums)

    js_payload = json.dumps(dataset, ensure_ascii=False).replace("</", "<\\/")
    if args.export_html:
        export_standalone_html(site_root, js_payload, args.export_html.resolve())
        print(f"\nExported standalone HTML report to: {args.export_html.resolve()}")

    if not args.dry_run:
        data_json_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        data_js_path.write_text("window.REPORT_DATASET = " + js_payload + ";\n", encoding="utf-8")
        today_utc8 = now_dt.astimezone(UTC8).strftime("%Y-%m-%d")
        card_updated = update_homepage_card_date(site_root / "index.html", today_utc8)
        print(f"\nUpdated {data_json_path} and {data_js_path}" + (" (+ index.html date)" if card_updated else ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
