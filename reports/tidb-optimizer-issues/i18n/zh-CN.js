SiteI18n.extend("zh-CN", {
  "report": {
    "meta": {
      "title": "TiDB 优化器开放 Issue 全景筛除、严重度与修复难度分级报告",
      "description": "针对 pingcap/tidb 优化器相关开放单据的去噪筛除、修复难度（Difficulty）与严重度（Severity）多维交互分级看板。"
    },
    "nav": {
      "dataJson": "增量数据源 (data.json)",
      "ghIssues": "GitHub Issues"
    },
    "header": {
      "title": "TiDB 优化器开放 Issue 全景筛除、严重度与修复难度分级报告",
      "subtitle": "覆盖 pingcap/tidb 优化器相关开放候选单据共 {totalAll} 条（含 sig/planner + type/bug 标准集 {totalCan} 条与统计信息 / SPM / 未分拣补充集 {totalSup} 条）。"
    },
    "sync": {
      "snapshotLabel": "快照拉取",
      "watermarkLabel": "最新 Issue 更新水位线",
      "queryLabel": "增量更新检索条件",
      "copyTitle": "点击复制 GitHub 增量过滤条件",
      "copied": "已复制: {query} ✓"
    },
    "kpi": {
      "scopedTotal": {
        "label": "当前口径候选总数",
        "hint": "全部为当前 OPEN 单据"
      },
      "realBugs": {
        "label": "真实有效优化器 Bug",
        "hint": "占比 {pct}% (E:{easy} · M:{med} · H:{hard})"
      },
      "highSev": {
        "label": "高危严重度 (S0+S1)",
        "hint": "致命 Critical {crit} · 严重 Major {maj}"
      },
      "prCoverage": {
        "label": "真实 Bug 修复 PR 覆盖",
        "hint": "在途 PR {open} 条 · 待认领 {unclaimed} 条"
      },
      "enhAndNoise": {
        "label": "Enhancement / 筛除噪声",
        "hint": "Fuzz {fuzz} · AI {ai} · 已修/其他 {oth}"
      }
    },
    "legend": {
      "easy": "真实 Bug · Easy",
      "med": "真实 Bug · Medium",
      "hard": "真实 Bug · Hard",
      "enh": "实为 Enhancement",
      "flt": "已筛除：Random / AI / 已修 / 非优化器"
    },
    "matrix": {
      "title": "🎯 真实 Bug 修复难度 (Difficulty) × 严重度 (Severity) 优先级矩阵",
      "subHtml": "点击任意单元格可直接联动过滤下方列表（浅黄底色为 <b>Easy × Critical/Major 高 ROI 速赢区</b>）",
      "corner": "修复难度 \\ 研判严重度",
      "colCrit": "🔥 Critical · 致命",
      "colMaj": "🟠 Major · 严重",
      "colMod": "🔵 Moderate · 中等",
      "colMin": "⚪ Minor · 轻微",
      "colTotal": "难度合计",
      "rowEasy": "🟢 Easy · 简单 (1~3d)",
      "rowMed": "🟡 Medium · 中等 (3~7d)",
      "rowHard": "🔴 Hard · 困难 (1~3w+)",
      "rowTotal": "严重度合计",
      "cellSub": "{wait} 待认领 · {inPr} 在途",
      "unclaimedSub": "{wait} 待认领",
      "resetSub": "点击重置矩阵",
      "activeBadge": "矩阵联动: {diff} × {sev}",
      "allDiff": "全部难度",
      "allSev": "全部严重度",
      "clearTitle": "清除矩阵筛选"
    },
    "rubric": {
      "summary": "筛除与分级口径说明（Triage Rubric）",
      "toggleHint": "展开 / 收起 ▾",
      "scope": {
        "title": "1. 噪声筛除与保留边界（Triage Scope）",
        "fuzzHtml": "<b>筛除 · Random / 差分 Fuzz</b>：由 SQLancer、TLP / NoREC / CERT、多层非常规类型集合运算、随机内建函数组合或手动黑名单关停优化规则构造的差分测试极端用例。",
        "aiHtml": "<b>筛除 · AI 静态猎奇边界</b>：基于源码静态审计刻意拼凑的表达式哈希碰撞、纪元极值哨兵或未默认开启开关的理论边界，常规业务 SQL 几乎不可达。",
        "nonOptHtml": "<b>筛除 · 非优化器 / 已修 / 无效</b>：归属执行器、DDL、存储客户端、UI 等非优化器模块的问题，主干已合入修复仅待关单/回移的单据，以及单测 Flaky 用例。",
        "keepHtml": "<b>边界保留与 Enhancement 区分</b>：虽由 Fuzz 约简或 AI 发现，但触发路径常规且造成<b>错结果、死锁、漏锁或崩溃</b>的问题一律保留为真实 Bug；结果正确、诉求为新增改写规则 / 访问路径 / 属性推导或语法支持的单据归入 <b>Enhancement</b>。"
      },
      "difficulty": {
        "title": "2. 修复难度分级（Difficulty · 工程成本）",
        "easyHtml": "<b>🟢 Easy · 简单（预计 1~3 天）</b>：根因清晰、改动收敛在单文件局部守卫或元数据补齐（如权限检查补漏、Plan Cache 键补齐会话变量、局部算术边界修正、告警与展示修复），不改变多阶段规则契约。",
        "medHtml": "<b>🟡 Medium · 中等（预计 3~7 天）</b>：涉及单子系统相邻阶段的不变量协同（如逻辑改写与列裁剪 Schema 映射、Range 提取与分区悲观锁下推、参数泛化与类型精度、分区 Global Stats 合并）。",
        "hardHtml": "<b>🔴 Hard · 困难（预计 1~3+ 周）</b>：牵涉跨模块重构、CBO 代价与超界外推模型权衡（易引发基准或生产计划回归）、<code>ANALYZE</code> 内存与系统表并发锁治理、MPP 隔离交互或单遍名称解析历史架构债，需配套设计方案与全量回归验证。"
      },
      "severity": {
        "title": "3. 严重度分级（Severity · 故障影响）",
        "critHtml": "<b>🔥 Critical · 致命（S0）</b>：进程 Panic / Crash、<code>ANALYZE</code> 或编译引发实例 OOM、后台核心协程永久退出、长时间阻塞全集群 GC、DML 错删改或串表、悲观事务 <code>FOR UPDATE</code> 静默漏锁、权限校验绕过。",
        "majHtml": "<b>🟠 Major · 严重（S1）</b>：只读 <code>SELECT</code> 返回错误结果、合法常见 SQL 报内部错误（如 <code>ERROR 1105</code>、隐式列解析失败）或统计信息元表死锁阻断执行、核心生产场景出现数量级计划退化。",
        "modHtml": "<b>🔵 Moderate · 中等（S2）</b>：一般性基数/代价估算偏差（计划次优但结果正确且无雪崩）、Plan Cache / SPM 未命中、Hint 导出回放局部失配或低频 MySQL 兼容性边缘差异。",
        "minHtml": "<b>⚪ Minor · 轻微（S3）</b>：Hint 告警文案、<code>EXPLAIN</code> / <code>SHOW STATS</code> / 慢日志 / 监控指标显示细节或周边诊断工具微瑕。<i>（若 GitHub 原始 <code>severity/*</code> 标签未标或与研判不一致，行内会附注 <code>GH原标</code> 供对照。）</i>"
      }
    },
    "filters": {
      "searchPlaceholder": "搜索 Issue #、PR #（如 #72862）、标题、@作者 或研判备注…",
      "searchAria": "搜索单据",
      "scopeAria": "统计口径",
      "scope": {
        "all": "全量候选池 ({count})",
        "canonical": "仅 sig/planner + type/bug ({count})",
        "customer": "仅客户生产反馈 ({count})",
        "borderline": "边界保留真 Bug ({count})"
      },
      "subAria": "子系统过滤",
      "subAll": "全部子系统",
      "sevAria": "严重度过滤",
      "sev": {
        "all": "全部严重度 (Severity)",
        "high": "🔥+🟠 Critical + Major (高优)",
        "critical": "🔥 Critical · 致命",
        "major": "🟠 Major · 严重",
        "moderate": "🔵 Moderate · 中等",
        "minor": "⚪ Minor · 轻微",
        "ghUnlabeled": "GitHub 原标签未标 severity/*"
      },
      "prAria": "PR 状态过滤",
      "pr": {
        "all": "全部 PR 状态",
        "openFix": "🟢 有在途修复 PR (OPEN/Draft)",
        "unclaimed": "🎯 无在途修复 PR (待认领)",
        "hasAny": "🔗 有任意关联内核 PR",
        "hasMerged": "🟣 含已合入关联 PR (MERGED)",
        "noPr": "⚪ 无任何关联 PR"
      },
      "updWinAria": "最近更新窗口",
      "updWin": {
        "all": "全部更新时间",
        "d1": "近 24 小时内更新",
        "d7": "近 7 天内更新",
        "d30": "近 30 天内更新",
        "d90": "近 90 天内更新"
      },
      "sincePrefix": "自",
      "sinceSuffix": "起更新",
      "sinceAria": "增量起始日期",
      "sortAria": "排序方式",
      "sort": {
        "updatedDesc": "排序：最后更新时间 ↓",
        "prioDesc": "排序：严重度优先 (S0→S3, 易→难)",
        "numDesc": "排序：Issue 编号 ↓ (最新创建)",
        "numAsc": "排序：Issue 编号 ↑ (最早积压)"
      }
    },
    "pills": {
      "REAL_ALL": "有效真实 Bug (全部)",
      "EASY": "Easy 简单",
      "MEDIUM": "Medium 中等",
      "HARD": "Hard 困难",
      "ENHANCEMENT": "实为 Enhancement",
      "FILTER_RANDOM_FUZZ": "筛除: Random/Fuzz",
      "FILTER_AI_OBSCURE": "筛除: AI 极端边界",
      "FILTER_NON_OPT_OR_FIXED": "筛除: 已修/非优化器",
      "ALL": "全部显示"
    },
    "status": {
      "count": "当前筛选命中 {matched} 条 Issue（口径内共 {scoped} 条）",
      "clickHint": "Issue 与 PR 标签均可直接点击打开 GitHub 页面（悬停 PR 可查看完整标题与状态）"
    },
    "table": {
      "colIssue": "Issue",
      "colCatSev": "难度 & 严重度",
      "colSub": "所属子模块",
      "colTitle": "标题、研判说明与可点击关联 PR",
      "colTime": "最后更新 / 创建信息",
      "ghSevNote": "GH原标: {val}",
      "ghUnlabeled": "未标",
      "tagCustomer": "客户反馈",
      "tagBorderline": "边界保留",
      "tagSupplemental": "补充池",
      "updatedPrefix": "更新 {time}",
      "createdPrefix": "创建 {date}",
      "empty": "无匹配 Issue，请调整筛选条件或点击重置矩阵"
    },
    "enums": {
      "cat": {
        "EASY": "真实 Bug · Easy",
        "MEDIUM": "真实 Bug · Medium",
        "HARD": "真实 Bug · Hard",
        "ENHANCEMENT": "实为 Enhancement",
        "FILTER_RANDOM_FUZZ": "已筛除 · Random/Fuzz",
        "FILTER_AI_OBSCURE": "已筛除 · AI Corner Case",
        "FILTER_NON_OPT_OR_FIXED": "已筛除 · 非优化器/已修/无效"
      },
      "diff": {
        "EASY": "简单 (1~3天)",
        "MEDIUM": "中等 (3~7天)",
        "HARD": "困难 (1~3+周)",
        "ENHANCEMENT": "功能/规则增强",
        "FILTER_RANDOM_FUZZ": "随机/差分测试极端用例",
        "FILTER_AI_OBSCURE": "AI 静态猎奇/极端边界",
        "FILTER_NON_OPT_OR_FIXED": "其他模块/已合入/Flaky"
      },
      "severity": {
        "CRITICAL": "Critical · 致命",
        "MAJOR": "Major · 严重",
        "MODERATE": "Moderate · 中等",
        "MINOR": "Minor · 轻微",
        "N/A": "N/A"
      },
      "subsystem": {
        "statistics": "统计信息与基数估算",
        "plan_cache_spm_hint": "Plan Cache / SPM / Hint",
        "logical_rewrite": "逻辑改写与子查询",
        "access_path_partition_lock": "访问路径 / 分区 / 锁",
        "cbo_cost_join_reorder": "CBO 代价与连接重排",
        "name_resolution_group_by": "名称解析与 GROUP BY 校验",
        "tiflash_mpp": "TiFlash / MPP"
      }
    }
  }
});
