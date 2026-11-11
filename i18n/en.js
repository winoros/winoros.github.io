SiteI18n.extend("en", {
  "common": {
    "langSwitchAria": "Switch interface language",
    "toggleTheme": "Theme",
    "toggleThemeAria": "Toggle light or dark theme",
    "backHome": "← winoros.github.io",
    "hostedOn": "Hosted on GitHub Pages"
  },
  "home": {
    "meta": {
      "title": "Yiding Cui (@winoros)",
      "description": "Yiding Cui (@winoros) — Database Kernel Engineer working on Query Optimizer & Distributed SQL at PingCAP (TiDB)."
    },
    "bioHtml": "Database Kernel Engineer at <b>PingCAP</b> · Focusing on the <b>TiDB</b> Query Optimizer, Cost &amp; Cardinality Estimation, Access Path Selection, and Plan Management.",
    "links": {
      "github": "GitHub Profile",
      "commits": "TiDB Commits",
      "prs": "Pull Requests"
    },
    "sections": {
      "reports": "Reports & Deep Dives",
      "focus": "Focus Areas"
    },
    "reports": {
      "tidbOptimizer": {
        "title": "TiDB Optimizer Open Issues: Triage, Severity & Fix Difficulty Report",
        "desc": "De-noised triage of open pingcap/tidb optimizer issues: filtering out SQLancer / differential fuzzing and obscure AI static-audit corner cases, separating enhancements from actionable bugs, mapping a 2D Difficulty × Severity priority matrix, and linking active fix PRs with incremental sync watermarks.",
        "tags": {
          "planner": "TiDB Planner",
          "triage": "Issue Triage",
          "explorer": "Interactive Explorer"
        }
      }
    },
    "focus": {
      "logical": {
        "title": "Logical & Physical Optimization",
        "desc": "Cascades / Volcano search, subquery decorrelation, predicate simplification & functional dependencies."
      },
      "access": {
        "title": "Access Paths & Range Extraction",
        "desc": "Ranger detachment, composite / prefix / partial / multi-valued indexes, and IndexMerge paths."
      },
      "stats": {
        "title": "Statistics, CBO & Plan Cache",
        "desc": "Histograms, TopN, out-of-range estimation, cost calibration, and prepared/instance plan caching."
      }
    }
  }
});
