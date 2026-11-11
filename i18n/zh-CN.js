SiteI18n.extend("zh-CN", {
  "common": {
    "langSwitchAria": "界面语言切换",
    "toggleTheme": "切换主题",
    "toggleThemeAria": "切换亮色或暗色主题",
    "backHome": "← winoros.github.io",
    "hostedOn": "托管于 GitHub Pages"
  },
  "home": {
    "meta": {
      "title": "Yiding Cui (@winoros) · 数据库内核研发",
      "description": "Yiding Cui (@winoros) — PingCAP (TiDB) 数据库内核研发工程师，专注于查询优化器与分布式 SQL。"
    },
    "bioHtml": "<b>PingCAP</b> 数据库内核研发工程师 · 专注于 <b>TiDB</b> 查询优化器、代价与基数估算、访问路径选择及执行计划管理。",
    "links": {
      "github": "GitHub 主页",
      "commits": "TiDB 提交记录",
      "prs": "Pull Requests"
    },
    "sections": {
      "reports": "分析报告与深度专题",
      "focus": "关注领域"
    },
    "reports": {
      "tidbOptimizer": {
        "title": "TiDB 优化器开放 Issue 全景筛除、严重度与修复难度分级报告",
        "desc": "对 pingcap/tidb 优化器相关开放单据进行去噪审阅：剥离 SQLancer / 差分 Fuzz 与 AI 静态猎奇边界，区分 Enhancement 与真实有效 Bug，构建 Difficulty × Severity 二维优先级矩阵，并关联在途修复 PR 与增量更新水位线。",
        "tags": {
          "planner": "TiDB 优化器",
          "triage": "Issue 研判",
          "explorer": "交互式看板"
        }
      }
    },
    "focus": {
      "logical": {
        "title": "逻辑与物理优化",
        "desc": "Cascades / Volcano 搜索框架、子查询去关联、谓词化简与函数依赖（FD）推导。"
      },
      "access": {
        "title": "访问路径与范围提取",
        "desc": "Ranger 谓词剥离、复合 / 前缀 / 部分 / 多值索引选择以及 IndexMerge 访问路径。"
      },
      "stats": {
        "title": "统计信息、CBO 与计划缓存",
        "desc": "直方图与 TopN、超界基数外推、代价模型校准，以及会话级 / 实例级 Plan Cache。"
      }
    }
  }
});
