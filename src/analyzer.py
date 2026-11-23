import json

INDICATOR_GROUPS = [
    {
        "category": "血脂代谢全套",
        "description": "反映全身脂质代谢周转、动脉粥样硬化风险及血管负荷",
        "items": [
            {"name": "甘油三酯", "abbr": "TG", "target": "< 1.70", "unit": "mmol/L"},
            {"name": "低密度脂蛋白胆固醇", "abbr": "LDL-C", "target": "< 3.40", "unit": "mmol/L"},
            {"name": "总胆固醇", "abbr": "TC", "target": "< 5.20", "unit": "mmol/L"},
            {"name": "高密度脂蛋白胆固醇", "abbr": "HDL-C", "target": "> 1.04", "unit": "mmol/L"},
        ]
    },
    {
        "category": "糖代谢与胰岛负担",
        "description": "评估血糖稳态与糖耐量风险",
        "items": [
            {"name": "葡萄糖(空腹)", "abbr": "GLU", "target": "3.90 - 6.10", "unit": "mmol/L"}
        ]
    },
    {
        "category": "肾功能与嘌呤代谢",
        "description": "反映肾小球滤过功能、体内酸碱及尿酸排泄状态",
        "items": [
            {"name": "尿酸", "abbr": "UA", "target": "208 - 428", "unit": "μmol/L"},
            {"name": "肌酐", "abbr": "CREA", "target": "57 - 97", "unit": "μmol/L"},
            {"name": "尿素", "abbr": "UREA", "target": "2.8 - 7.2", "unit": "mmol/L"},
            {"name": "估算肾小球滤过率", "abbr": "eGFR", "target": "> 90", "unit": "mL/min"}
        ]
    },
    {
        "category": "肝胆功能与细胞修护",
        "description": "反映肝实质细胞通透性、解毒与排泄负荷",
        "items": [
            {"name": "丙氨酸氨基转移酶", "abbr": "ALT", "target": "9 - 50", "unit": "U/L"},
            {"name": "天门冬氨酸氨基转移酶", "abbr": "AST", "target": "15 - 40", "unit": "U/L"},
            {"name": "γ-谷氨酰基转移酶", "abbr": "GGT", "target": "10 - 60", "unit": "U/L"},
            {"name": "总胆红素", "abbr": "TBIL", "target": "≤ 26.0", "unit": "μmol/L"},
            {"name": "白蛋白", "abbr": "ALB", "target": "40.0 - 55.0", "unit": "g/L"}
        ]
    }
]

def load_extracted_data(files):
    all_reports = []
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            all_reports.append(json.load(f))
    return all_reports

def build_full_comparison(reports):
    # Sort reports chronologically
    reports = sorted(reports, key=lambda x: x.get("report_date", ""))
    report_dates = [r.get("report_date", "") for r in reports]

    grouped_results = []

    for group in INDICATOR_GROUPS:
        group_items = []
        for target in group["items"]:
            history = []
            for rep in reports:
                date = rep.get("report_date", "")
                val = None
                status = "normal"
                ref_range = target["target"]
                for item in rep.get("items", []):
                    # match standard or alias
                    if (target["name"] in item.get("name", "")) or (item.get("abbr") and item.get("abbr") == target["abbr"]):
                        val = item.get("value")
                        status = item.get("status", "normal")
                        if item.get("ref_range"):
                            ref_range = item.get("ref_range")
                        break
                history.append({
                    "date": date,
                    "value": val,
                    "status": status,
                    "ref_range": ref_range
                })

            # Trend logic
            valid_vals = []
            for h in history:
                if h["value"] is not None:
                    try:
                        valid_vals.append(float(str(h["value"]).replace("*", "").strip()))
                    except ValueError:
                        pass

            trend_status = "平稳"
            badge_class = "badge-normal"
            if len(valid_vals) >= 2:
                diff = valid_vals[-1] - valid_vals[0]
                first_val = valid_vals[0]
                last_val = valid_vals[-1]
                
                if target["name"] in ["低密度脂蛋白胆固醇", "总胆固醇"]:
                    if diff < -0.3:
                        trend_status = "大幅改善 ↓"
                        badge_class = "badge-good"
                    elif diff > 0.3:
                        trend_status = "需关注 ↑"
                        badge_class = "badge-warn"
                elif target["name"] == "甘油三酯":
                    if last_val > 1.70:
                        trend_status = "偏高升高 ↑"
                        badge_class = "badge-danger"
                    else:
                        trend_status = "正常"
                        badge_class = "badge-good"
                elif target["name"] == "尿酸":
                    if diff < -20:
                        trend_status = "稳步下降 ↓"
                        badge_class = "badge-good"
                    elif last_val > 420:
                        trend_status = "偏高警戒 ↑"
                        badge_class = "badge-warn"
                else:
                    if history[-1]["status"] == "high":
                        trend_status = "略偏高"
                        badge_class = "badge-warn"
                    elif history[-1]["status"] == "low":
                        trend_status = "略偏低"
                        badge_class = "badge-warn"
                    else:
                        trend_status = "保持正常"
                        badge_class = "badge-good"

            group_items.append({
                "name": target["name"],
                "abbr": target["abbr"],
                "unit": target["unit"],
                "target": target["target"],
                "history": history,
                "latest_value": history[-1]["value"] if history else None,
                "latest_status": history[-1]["status"] if history else "normal",
                "trend_status": trend_status,
                "badge_class": badge_class
            })

        grouped_results.append({
            "category": group["category"],
            "description": group["description"],
            "items": group_items
        })

    return {
        "report_dates": report_dates,
        "grouped_results": grouped_results
    }
