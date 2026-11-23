import json
from src.text_cleaner import clean_forbidden_and_recommended, replace_abbreviations, ABNORMAL_EXPLANATIONS

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>个人健康数据对比与滋补食养指引报告</title>
  <style>
    :root {
      --primary: #0f766e;
      --primary-light: #f0fdfa;
      --primary-border: #99f6e4;
      --accent: #b45309;
      --danger: #b91c1c;
      --danger-bg: #fff1f2;
      --danger-border: #fecdd3;
      --success: #15803d;
      --success-bg: #f0fdf4;
      --success-border: #bbf7d0;
      --card-bg: #ffffff;
      --bg: #f8fafc;
      --text-main: #0f172a;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --radius: 14px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      background: #eef2f6;
      color: var(--text-main);
      line-height: 1.6;
      padding: 16px 8px;
      display: flex;
      justify-content: center;
    }
    .report-card {
      max-width: 620px;
      width: 100%;
      background: var(--card-bg);
      border-radius: var(--radius);
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.06);
      overflow: hidden;
      border: 1px solid var(--border);
    }
    /* Header */
    .header {
      background: linear-gradient(135deg, #134e4a 0%, #0f766e 100%);
      color: #fff;
      padding: 28px 20px 22px;
      position: relative;
    }
    .header-badge {
      display: inline-block;
      background: rgba(255, 255, 255, 0.18);
      backdrop-filter: blur(4px);
      padding: 3px 10px;
      border-radius: 12px;
      font-size: 11px;
      letter-spacing: 0.8px;
      margin-bottom: 8px;
      font-weight: 600;
    }
    .header h1 {
      font-size: 21px;
      font-weight: 700;
      margin-bottom: 6px;
      letter-spacing: -0.3px;
    }
    .header-desc {
      font-size: 13px;
      opacity: 0.9;
    }

    /* Overall Summary */
    .summary-section {
      padding: 18px 20px 10px;
    }
    .summary-box {
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-left: 4px solid var(--primary);
      padding: 14px 16px;
      border-radius: 8px;
      font-size: 14px;
      color: #334155;
      line-height: 1.7;
    }
    .summary-box strong {
      color: var(--primary);
      display: block;
      margin-bottom: 4px;
      font-size: 14px;
    }

    /* Section Headers */
    .part-divider {
      background: #f1f5f9;
      padding: 10px 20px;
      font-size: 13px;
      font-weight: 700;
      color: #475569;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      border-top: 1px solid var(--border);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      gap: 6px;
    }

    /* Data Tables Section */
    .group-block {
      padding: 16px 20px 6px;
    }
    .group-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 8px;
    }
    .group-title {
      font-size: 16px;
      font-weight: 700;
      color: var(--text-main);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .group-desc {
      font-size: 12px;
      color: var(--text-muted);
    }
    .data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      background: #fff;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      overflow: hidden;
      margin-bottom: 10px;
    }
    .data-table th, .data-table td {
      padding: 8px 6px;
      text-align: center;
      border-bottom: 1px solid #f1f5f9;
    }
    .data-table th {
      background: #f8fafc;
      color: #64748b;
      font-weight: 600;
      font-size: 11px;
    }
    .data-table tr:last-child td {
      border-bottom: none;
    }
    .td-name {
      text-align: left !important;
      padding-left: 10px !important;
      font-weight: 600;
      color: #1e293b;
    }
    .val-normal { color: #0f172a; }
    .val-highlight { color: var(--primary); font-weight: 700; }
    .val-danger { color: var(--danger); font-weight: 700; }

    .tag-badge {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
    }
    .badge-good { background: #dcfce7; color: #15803d; }
    .badge-warn { background: #fef3c7; color: #b45309; }
    .badge-danger { background: #fee2e2; color: #b91c1c; }
    .badge-normal { background: #f1f5f9; color: #64748b; }

    .category-insight {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      padding: 12px 14px;
      border-radius: 8px;
      font-size: 13px;
      color: #334155;
      line-height: 1.6;
      margin-bottom: 10px;
    }

    /* Abnormal Item Card */
    .abnormal-box {
      background: #fff5f5;
      border: 1px solid #fed7d7;
      border-left: 4px solid #e53e3e;
      border-radius: 6px;
      padding: 10px 12px;
      font-size: 12px;
      color: #742a2a;
      line-height: 1.6;
      margin-bottom: 14px;
    }
    .abnormal-header {
      font-weight: 700;
      color: #c53030;
      margin-bottom: 4px;
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 13px;
    }
    .abnormal-item-line {
      margin-bottom: 4px;
    }
    .abnormal-item-line:last-child {
      margin-bottom: 0;
    }

    /* Tonic Section */
    .tonic-category-card {
      margin: 16px 20px 20px;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
    }
    .tc-header {
      padding: 12px 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #f8fafc;
      border-bottom: 1px solid #e2e8f0;
    }
    .tc-title {
      font-size: 15px;
      font-weight: 700;
      color: #1e293b;
    }
    .tc-status {
      font-size: 12px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 6px;
    }
    .status-red { background: var(--danger-bg); color: var(--danger); border: 1px solid var(--danger-border); }
    .status-green { background: var(--success-bg); color: var(--success); border: 1px solid var(--success-border); }

    .tc-body {
      padding: 14px 16px;
    }
    .sub-advice-box {
      margin-bottom: 12px;
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 13px;
      line-height: 1.6;
    }
    .sub-advice-box:last-child {
      margin-bottom: 0;
    }
    .box-forbidden {
      background: #fef2f2;
      border-left: 3px solid #ef4444;
      color: #7f1d1d;
    }
    .box-recommend {
      background: #f0fdf4;
      border-left: 3px solid #22c55e;
      color: #14532d;
    }
    .box-label {
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 4px;
      margin-bottom: 6px;
      font-size: 13px;
    }

    /* Point list */
    .point-list {
      margin: 0;
      padding-left: 18px;
    }
    .point-list li {
      margin-bottom: 4px;
    }
    .point-list li:last-child {
      margin-bottom: 0;
    }

    /* Footer */
    .footer {
      background: #f8fafc;
      border-top: 1px solid var(--border);
      padding: 18px 20px;
      text-align: center;
    }
    .next-plan {
      font-size: 13px;
      font-weight: 700;
      color: var(--primary);
      margin-bottom: 6px;
    }
    .disclaimer {
      font-size: 11px;
      color: #94a3b8;
      line-height: 1.5;
    }
  </style>
</head>
<body>
  <div class="report-card">
    <!-- Header -->
    <div class="header">
      <div class="header-badge">HEALTH DATA MATRIX & TONIC GUIDE</div>
      <h1>个人健康数据对比与滋补食养指引</h1>
      <div class="header-desc">
        历期跨度：2025.09 - 2026.10 ｜ 覆盖肝、肾、糖、脂四大核心系统
      </div>
    </div>

    <!-- Overall Summary -->
    <div class="summary-section">
      <div class="summary-box">
        <strong>📋 全面数据综合评估：</strong>
        {{overall_summary}}
      </div>
    </div>

    <!-- Part 1: Data Comparison -->
    <div class="part-divider">
      <span>📊 第一部分：全系统健康数据横向对比</span>
    </div>

    <div class="data-section">
      {{data_groups_html}}
    </div>

    <!-- Part 2: Tonic Guidance -->
    <div class="part-divider" style="background:#f0fdfa; color:#0f766e; border-top: 2px solid #0f766e;">
      <span>🍵 第二部分：分项目精准滋补建议（禁忌 vs 推荐）</span>
    </div>

    <div class="tonic-section">
      {{tonic_cards_html}}
    </div>

    <!-- Footer -->
    <div class="footer">
      <div class="next-plan">📅 复查建议：{{next_review_plan}}</div>
      <div class="disclaimer">
        声明：{{disclaimer}}
      </div>
    </div>
  </div>
</body>
</html>
"""

def render_project_tonic_html(comparison_data, report_data):
    # Flatten nested keys from DeepSeek response
    p1 = report_data.get("part1_health_analysis", {})
    overall_summary = p1.get("overall_summary", report_data.get("overall_summary", ""))
    cat_analyses = p1.get("category_analyses", report_data.get("category_analyses", []))

    p2 = report_data.get("part2_nourishment_guidance", report_data.get("tonic_categories", []))
    p3 = report_data.get("part3_followup", {})
    next_review = p3.get("next_review_plan", report_data.get("next_review_plan", "建议 60-90 天后复查血脂四项。"))
    disclaimer = p3.get("disclaimer", report_data.get("disclaimer", "本报告基于体检数据整理，仅作日常膳食滋补与生活方式参考，不构成医疗诊断或用药依据。"))

    # Map interpretations with fuzzy keyword matching
    cat_insight_map = {}
    for item in cat_analyses:
        cname = item.get("category", "")
        text = item.get("interpretation") or item.get("analysis") or ""
        cat_insight_map[cname] = text

    def get_category_insight(group_cat_name):
        # 1. Direct match
        if group_cat_name in cat_insight_map:
            return cat_insight_map[group_cat_name]
        # 2. Key mapping
        mapping = {
            "血脂代谢全套": "血脂代谢",
            "糖代谢与胰岛负担": "糖代谢",
            "肾功能与嘌呤代谢": "肾功能与尿酸",
            "肝胆功能与细胞修护": "肝胆代谢"
        }
        target_key = mapping.get(group_cat_name)
        if target_key and target_key in cat_insight_map:
            return cat_insight_map[target_key]
        # 3. Substring matching
        for k, v in cat_insight_map.items():
            if ("肾" in group_cat_name and "肾" in k) or ("肝" in group_cat_name and "肝" in k) or ("脂" in group_cat_name and "脂" in k) or ("糖" in group_cat_name and "糖" in k):
                return v
        return ""

    # 1. Build Data Groups HTML
    dates = comparison_data.get("report_dates", [])
    date_headers = "".join([f"<th>{d[2:]}</th>" for d in dates])

    groups_html_list = []
    for grp in comparison_data.get("grouped_results", []):
        cat_name = grp["category"]
        rows_html = []
        abnormal_items_in_group = []

        for it in grp["items"]:
            val_tds = []
            for h in it["history"]:
                val = h["value"]
                status = h["status"]
                cls = "val-normal"
                if it["name"] == "甘油三酯" and status == "high":
                    cls = "val-danger"
                elif it["name"] in ["低密度脂蛋白胆固醇", "总胆固醇", "尿酸"] and val is not None:
                    cls = "val-highlight"
                val_tds.append(f"<td class='{cls}'>{val if val is not None else '-'}</td>")

            rows_html.append(f"""
            <tr>
              <td class="td-name">
                <div>{it['name']}</div>
                <div style="font-size:10px; color:#94a3b8; font-weight:normal;">{it['abbr']} ({it['unit']})</div>
              </td>
              {''.join(val_tds)}
              <td style="color:#64748b; font-size:11px;">{it['target']}</td>
              <td><span class="tag-badge {it['badge_class']}">{it['trend_status']}</span></td>
            </tr>
            """)

            # Check if this indicator is abnormal in latest report
            latest_val = it.get("latest_value")
            target_config = ABNORMAL_EXPLANATIONS.get(it["name"])
            if target_config and target_config["condition"](latest_val):
                abnormal_items_in_group.append({
                    "name": it["name"],
                    "value": latest_val,
                    "unit": it["unit"],
                    "meaning": target_config["indicator_meaning"],
                    "consequence": target_config["possible_consequences"]
                })

        # Match category insight
        insight_text = replace_abbreviations(get_category_insight(cat_name))

        # Build abnormal explanations block if any
        abnormal_html = ""
        if abnormal_items_in_group:
            ab_lines = []
            for ab in abnormal_items_in_group:
                ab_lines.append(f"""
                <div class="abnormal-item-line">
                  <strong>⚠️ 异常指标解读【{ab['name']} 当前值：{ab['value']} {ab['unit']}】：</strong><br/>
                  • <strong>指标含义：</strong>{ab['meaning']}<br/>
                  • <strong>潜在后果与风险：</strong>{ab['consequence']}
                </div>
                """)
            abnormal_html = f"""
            <div class="abnormal-box">
              <div class="abnormal-header">⚠️ 需关注的非正常指标警示与风险评估：</div>
              {''.join(ab_lines)}
            </div>
            """

        groups_html_list.append(f"""
        <div class="group-block">
          <div class="group-header">
            <div class="group-title">{cat_name}</div>
            <div class="group-desc">{grp['description']}</div>
          </div>
          <table class="data-table">
            <thead>
              <tr>
                <th style="text-align:left; padding-left:10px;">指标项目</th>
                {date_headers}
                <th>参考目标</th>
                <th>趋势判定</th>
              </tr>
            </thead>
            <tbody>
              {''.join(rows_html)}
            </tbody>
          </table>
          <div class="category-insight">
            💡 <strong>系统解读：</strong>{insight_text}
          </div>
          {abnormal_html}
        </div>
        """)

    data_groups_html = "".join(groups_html_list)

    # 2. Build Tonic Guidance Cards HTML
    tonic_cards = []
    for tc in p2:
        badge_cls = "status-red" if tc.get("badge_type") == "red" else "status-green"
        
        # Clean forbidden and recommended points
        cleaned_forbidden = clean_forbidden_and_recommended(tc.get("forbidden_guidance", ""))
        cleaned_recommended = clean_forbidden_and_recommended(tc.get("recommended_guidance", ""))

        tonic_cards.append(f"""
        <div class="tonic-category-card">
          <div class="tc-header">
            <div class="tc-title">{tc['category_name']}</div>
            <div class="tc-status {badge_cls}">{tc['status']}</div>
          </div>
          <div class="tc-body">
            <div class="sub-advice-box box-forbidden">
              <div class="box-label">🚫 禁忌 / 需避坑：</div>
              <div>{cleaned_forbidden}</div>
            </div>
            <div class="sub-advice-box box-recommend">
              <div class="box-label">✅ 推荐品类与科学吃法：</div>
              <div>{cleaned_recommended}</div>
            </div>
          </div>
        </div>
        """)

    tonic_cards_html = "".join(tonic_cards)

    # 3. Replace in Template
    rendered = HTML_TEMPLATE
    rendered = rendered.replace("{{overall_summary}}", replace_abbreviations(overall_summary))
    rendered = rendered.replace("{{data_groups_html}}", data_groups_html)
    rendered = rendered.replace("{{tonic_cards_html}}", tonic_cards_html)
    rendered = rendered.replace("{{next_review_plan}}", replace_abbreviations(next_review))
    rendered = rendered.replace("{{disclaimer}}", replace_abbreviations(disclaimer))

    return rendered
