"""确定性规则引擎：跨年指标趋势分析 + 正常值内连续恶化预警 + 药食同源红绿灯匹配。"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional


CODE_ALIASES = {
    "HBA1C": "HbA1c",
    "GHB": "HbA1c",
    "LDL": "LDL-C",
    "LDL_C": "LDL-C",
    "LDLC": "LDL-C",
    "HDL": "HDL-C",
    "HDL_C": "HDL-C",
    "HDLC": "HDL-C",
    "GLU": "FBG",
    "FPG": "FBG",
    "CHOL": "TC",
    "TCHO": "TC",
    "TRIG": "TG",
    "URIC": "UA",
    "CREA": "Cr",
    "SCR": "Cr",
    "CR": "Cr",
    "VITD": "VitD",
    "25-OH-VD": "VitD",
    "25-OH-D": "VitD",
    "25(OH)D": "VitD",
    "VD": "VitD",
    "CA": "Ca",
}


def _normalize_code(raw_code: str) -> str:
    c = raw_code.strip()
    upper = c.upper()
    return CODE_ALIASES.get(upper, c)


def load_rules(rules_path: Path) -> Dict[str, Any]:
    return json.loads(rules_path.read_text(encoding="utf-8"))


def analyze_trends(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """聚合跨年指标，识别：①最新异常项；②正常值内连续单边恶化项；③已改善项。"""
    sorted_reports = sorted(reports, key=lambda r: r.get("report_date", ""))
    series_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    seen_code_date: Dict[str, set] = defaultdict(set)
    meta_map: Dict[str, Dict[str, Any]] = {}
    all_findings: List[Dict[str, Any]] = []

    for rep in sorted_reports:
        rdate = rep.get("report_date", "未知日期")
        source = rep.get("source_file", "体检报告")
        for ind in rep.get("indicators", []):
            code = _normalize_code(str(ind.get("code") or ind.get("name") or ""))
            if not code:
                continue
            val = ind.get("value")
            if val is None:
                continue
            try:
                num_val = float(val)
            except (TypeError, ValueError):
                continue

            if rdate in seen_code_date[code]:
                continue
            seen_code_date[code].add(rdate)

            series_map[code].append(
                {
                    "date": rdate,
                    "value": num_val,
                    "ref_low": ind.get("ref_low"),
                    "ref_high": ind.get("ref_high"),
                    "page": ind.get("page", ""),
                    "source_file": source,
                }
            )
            meta_map[code] = {
                "code": code,
                "name": ind.get("name", code),
                "unit": ind.get("unit", ""),
                "ref_low": ind.get("ref_low"),
                "ref_high": ind.get("ref_high"),
            }

        for f in rep.get("findings", []):
            summary = str(f.get("summary", "")).strip()
            if not summary:
                continue
            all_findings.append(
                {
                    "date": rdate,
                    "section": f.get("section", "影像/超声"),
                    "summary": summary,
                    "page": f.get("page", ""),
                    "source_file": source,
                }
            )

    indicators_analysis: List[Dict[str, Any]] = []
    for code, points in series_map.items():
        meta = meta_map[code]
        latest = points[-1]
        ref_high = latest.get("ref_high")
        ref_low = latest.get("ref_low")
        val = latest["value"]

        is_high = ref_high is not None and val > float(ref_high)
        is_low = ref_low is not None and val < float(ref_low)

        # 判断是否“在参考值内，但连续 >= 2 次单边逼近上限”
        borderline_worsening = False
        if not is_high and not is_low and len(points) >= 3 and ref_high is not None:
            last3 = [p["value"] for p in points[-3:]]
            if last3[0] < last3[1] < last3[2] and last3[2] >= float(ref_high) * 0.88:
                borderline_worsening = True
        elif not is_high and not is_low and len(points) == 2 and ref_high is not None:
            if points[0]["value"] < points[1]["value"] and points[1]["value"] >= float(ref_high) * 0.92:
                borderline_worsening = True

        # 判断是否较上一年明显回落改善
        improving = False
        delta_prev = None
        if len(points) >= 2:
            prev = points[-2]["value"]
            delta_prev = round(val - prev, 3)
            if ref_high is not None and prev > float(ref_high) and val < prev:
                improving = True

        if is_high:
            status = "high"
            status_label = "偏高"
        elif is_low:
            status = "low"
            status_label = "偏低"
        elif borderline_worsening:
            status = "borderline_worsening"
            status_label = "临界上升预警"
        elif improving:
            status = "improving"
            status_label = "已回落改善"
        else:
            status = "normal"
            status_label = "正常稳态"

        indicators_analysis.append(
            {
                "code": code,
                "name": meta["name"],
                "unit": meta["unit"],
                "ref_low": ref_low,
                "ref_high": ref_high,
                "latest_value": val,
                "latest_date": latest["date"],
                "latest_page": latest["page"],
                "delta_prev": delta_prev,
                "status": status,
                "status_label": status_label,
                "points": points,
            }
        )

    # 排序：异常与临界预警置顶，其次已改善，最后正常
    priority = {"high": 0, "low": 1, "borderline_worsening": 2, "improving": 3, "normal": 4}
    indicators_analysis.sort(key=lambda x: (priority.get(x["status"], 9), x["code"]))

    # 每个影像/检查部位保留最新一条结论（避免新血检日期覆盖掉此前的超声/CT结论）
    latest_by_section: Dict[str, Dict[str, Any]] = {}
    for f in all_findings:
        sec = f.get("section", "影像/超声")
        latest_by_section[sec] = f
    latest_findings = list(latest_by_section.values())

    unique_dates = sorted({r.get("report_date", "") for r in sorted_reports if r.get("report_date") and r.get("report_date") != "unknown"})

    return {
        "report_dates": unique_dates,
        "indicators": indicators_analysis,
        "latest_findings": latest_findings,
        "all_findings": all_findings,
    }


def _match_numeric_trigger(trigger: Dict[str, Any], indicator: Dict[str, Any], gender: str) -> bool:
    t_gender = trigger.get("gender", "any")
    if t_gender != "any" and gender and t_gender != gender:
        return False
    if indicator["code"].upper() != str(trigger.get("code", "")).upper():
        return False

    val = indicator["latest_value"]
    threshold = float(trigger["value"])
    op = trigger.get("op", ">")
    if op == ">":
        return val > threshold
    if op == ">=":
        return val >= threshold
    if op == "<":
        return val < threshold
    if op == "<=":
        return val <= threshold
    return False


def match_food_therapy_rules(
    trends: Dict[str, Any],
    profile: Dict[str, Any],
    rules_config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """根据最新指标、临界上升指标及最新影像结论，确定性匹配红绿灯食养规则。"""
    gender = str(profile.get("gender", "any"))
    indicators = trends.get("indicators", [])
    findings = trends.get("latest_findings", [])

    matched_rules: List[Dict[str, Any]] = []
    for rule in rules_config.get("rules", []):
        reasons: List[str] = []
        for trigger in rule.get("triggers", []):
            if "code" in trigger:
                for ind in indicators:
                    if _match_numeric_trigger(trigger, ind, gender):
                        reasons.append(f"{ind['name']}({ind['code']}) 最新值 {ind['latest_value']} {ind['unit']}（{ind['status_label']}）")
                    elif (
                        ind["code"].upper() == str(trigger["code"]).upper()
                        and ind["status"] == "borderline_worsening"
                    ):
                        reasons.append(f"{ind['name']}({ind['code']}) 虽在参考值内但连续上升至 {ind['latest_value']} {ind['unit']}（临界预警）")
            elif "finding_keyword" in trigger:
                kw = trigger["finding_keyword"]
                for f in findings:
                    if kw in f.get("summary", ""):
                        reasons.append(f"{f['section']}：{f['summary']}")

        if reasons:
            rule_copy = dict(rule)
            rule_copy["matched_reasons"] = list(dict.fromkeys(reasons))
            matched_rules.append(rule_copy)

    return matched_rules


def resolve_constitution_hints(
    selected_ids: List[str],
    rules_config: Dict[str, Any],
) -> List[Dict[str, str]]:
    opt_map = {opt["id"]: opt for opt in rules_config.get("constitution_options", [])}
    return [opt_map[cid] for cid in selected_ids if cid in opt_map]
