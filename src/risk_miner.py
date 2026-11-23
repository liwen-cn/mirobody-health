"""Three-Layer Proactive Health Risk Mining Engine.

Layer 1 (Red Flags):   Explicit out-of-range lab values & abnormal qualitative findings.
Layer 2 (Yellow Flags): Silent borderline values (top/bottom 15-18% of range, clinical
                        early-warning cutoffs like eGFR < 90 or HbA1c >= 5.7) and
                        cross-date unfavorable trends.
Layer 3 (System & Rule Aggregation): Groups ALL observations into medical systems,
                        extracts protective highlights, and matches food-therapy rules.
"""

import os
import re
from collections import defaultdict


# Metrics where being near the LOWER bound (0 or low) is healthy/desirable, not a deficiency risk.
LOWER_IS_BETTER_KEYWORDS = (
    "甘油三酯", "总胆固醇", "低密度脂蛋白", "胆红素", "氨基转移酶", "转氨酶", "转肽酶",
    "磷酸酶", "尿酸", "肌酐", "尿素", "C反应蛋白", "沉降率", "嗜酸", "嗜碱", "单核",
    "尿白蛋白", "白细胞(WBC", "红细胞(RBC", "上皮细胞", "管型", "细菌", "肌红蛋白",
    "肌酸激酶", "肌钙蛋白", "同型半胱氨酸", "甲胎蛋白", "癌胚抗原",
)

# Metrics where being near the UPPER bound is healthy/desirable (higher is better).
HIGHER_IS_BETTER_KEYWORDS = (
    "高密度脂蛋白", "估算肾小球滤过率", "25-羟基维生素D", "维生素D", "白蛋白",
)

SYSTEM_RULES = [
    ("糖代谢与胰岛负荷", ("糖化血红蛋白", "葡萄糖", "血糖", "胰岛素", "C肽")),
    ("血脂代谢全套", ("甘油三酯", "总胆固醇", "低密度脂蛋白", "高密度脂蛋白", "脂蛋白", "载脂蛋白")),
    ("肾功能与泌尿系统", ("尿酸", "肌酐", "尿素", "肾小球滤过率", "尿白蛋白", "尿蛋白", "尿葡萄糖", "尿胆", "酮体", "亚硝酸盐", "隐血", "比重", "酸碱度", "管型", "上皮细胞", "细菌", "电导率", "颜色", "浊度", "红细胞(RBC-2)", "白细胞(WBC-2)", "白细胞(LEU)")),
    ("肝胆功能与蛋白代谢", ("氨基转移酶", "转氨酶", "胆红素", "总蛋白", "白蛋白", "球蛋白", "碱性磷酸酶", "谷氨酰")),
    ("心血管与心电图", ("心率", "心电图", "窦性", "QRS", "QT", "RV5", "Rv5", "P-R", "肌红蛋白", "肌酸激酶", "肌钙蛋白", "血压")),
    ("血常规与炎症免疫", ("白细胞", "红细胞", "血红蛋白", "血小板", "中性粒", "淋巴细胞", "单核细胞", "嗜酸", "嗜碱", "C反应蛋白", "沉降率")),
    ("微量元素与维生素营养", ("全血铜", "全血锌", "全血钙", "全血镁", "全血铁", "钙(Ca)", "钾", "钠", "氯", "维生素D", "叶酸", "铁蛋白")),
]


def clean_name(name_text):
    if not name_text:
        return ""
    return re.sub(r"^\*+\s*", "", name_text.strip())


def parse_numeric_value(val_text, val_num=None):
    if val_num is not None:
        try:
            return float(val_num)
        except (ValueError, TypeError):
            pass
    if not val_text:
        return None
    s = str(val_text).strip()
    m = re.match(r"^[<>≤≥]?\s*(-?\d+(?:\.\d+)?)$", s)
    if m:
        return float(m.group(1))
    return None


def parse_ref_range(ref_text, ref_low=None, ref_high=None):
    """Parse reference range into (low, high, mode) where mode is 'closed' | 'upper' | 'lower' | 'qualitative' | 'none'."""
    low = float(ref_low) if ref_low is not None else None
    high = float(ref_high) if ref_high is not None else None
    if low is not None and high is not None:
        return low, high, "closed"
    if high is not None:
        return None, high, "upper"
    if low is not None:
        return low, None, "lower"

    if not ref_text:
        return None, None, "none"

    txt = ref_text.strip()
    if txt in ("/", "-", "--", "无"):
        return None, None, "none"

    # Handle Chinese prefixed ranges like "男|≥18岁|629.6-1039.7"
    if "|" in txt:
        txt = txt.split("|")[-1].strip()

    # Closed range: "4.0--6.0", "57-97", "0.02~0.52"
    m = re.match(r"^(-?\d+(?:\.\d+)?)\s*(?:--|-|~|～)\s*(-?\d+(?:\.\d+)?)$", txt)
    if m:
        return float(m.group(1)), float(m.group(2)), "closed"

    # Upper bound: "<1.70", "≤26", "<= 30"
    m = re.match(r"^(?:<|<=|≤)\s*(-?\d+(?:\.\d+)?)$", txt)
    if m:
        return None, float(m.group(1)), "upper"

    # Lower bound: ">1.0", ">=50", "≥90"
    m = re.match(r"^(?:>|>=|≥)\s*(-?\d+(?:\.\d+)?)$", txt)
    if m:
        return float(m.group(1)), None, "lower"

    return None, None, "qualitative"


def classify_system(name):
    # Exact special check for single-letter ECG P wave
    if name in ("P", "PR", "P-R"):
        return "心血管与心电图"
    for sys_name, keywords in SYSTEM_RULES:
        for kw in keywords:
            if kw in name:
                return sys_name
    return "其他检查项目"


def _is_lower_better(name):
    return any(kw in name for kw in LOWER_IS_BETTER_KEYWORDS)


def _is_higher_better(name):
    return any(kw in name for kw in HIGHER_IS_BETTER_KEYWORDS)


def evaluate_observation(obs, user_profile=None):
    """Evaluate a single observation and assign risk_level: 'red' | 'yellow' | 'normal' | 'info'."""
    name = clean_name(obs.get("name_text", ""))
    val_text = str(obs.get("value_text", "")).strip()
    unit = obs.get("unit_text", "") or obs.get("unit_canonical", "")
    ref_text = obs.get("ref_text", "")
    flag_text = obs.get("flag_text", "")
    gender = str((user_profile or {}).get("gender") or "").strip()

    val_num = parse_numeric_value(val_text, obs.get("value_num"))
    low, high, mode = parse_ref_range(ref_text, obs.get("ref_low"), obs.get("ref_high"))

    risk_level = "normal"
    direction = ""
    reason = ""
    range_pct = None

    # 1. Explicit qualitative checks (e.g. ref='阴性', val='10(+/-)')
    if mode == "qualitative":
        if "阴性" in ref_text:
            if val_text in ("阴性", "-", "(-)", "正常"):
                risk_level = "normal"
            else:
                risk_level = "red"
                direction = "异常阳性"
                reason = f"参考为{ref_text}，实测为 {val_text}"
        elif "清晰" in ref_text and "清晰" not in val_text:
            risk_level = "yellow"
            direction = "性状异常"
            reason = f"参考为{ref_text}，实测为 {val_text}"
        else:
            risk_level = "normal"

    # 2. Quantitative checks
    elif val_num is not None and mode in ("closed", "upper", "lower"):
        # Handle comparator like "< 0.20"
        is_less_than = val_text.startswith("<")

        if mode == "closed":
            if val_num > high:
                risk_level = "red"
                direction = "偏高 ↑"
                reason = f"超出参考上限（{val_num} > {high}）"
            elif val_num < low and not is_less_than:
                risk_level = "red"
                direction = "偏低 ↓"
                reason = f"低于参考下限（{val_num} < {low}）"
            else:
                span = high - low
                if span > 0:
                    range_pct = round((val_num - low) / span * 100, 1)
                    if range_pct >= 82.0 and not _is_higher_better(name):
                        risk_level = "yellow"
                        direction = "临界偏高 ↗"
                        reason = f"虽在正常范围，但已达参考区间 {range_pct}% 高位（上限 {high}）"
                    elif range_pct <= 15.0 and not _is_lower_better(name) and not is_less_than:
                        risk_level = "yellow"
                        direction = "临界偏低 ↘"
                        reason = f"虽在正常范围，但已处于参考区间 {range_pct}% 低位（下限 {low}）"
        elif mode == "upper":
            if val_num > high and not is_less_than:
                risk_level = "red"
                direction = "偏高 ↑"
                reason = f"超出参考上限（{val_num} > {high}）"
            elif not is_less_than and high > 0 and (val_num / high) >= 0.85:
                risk_level = "yellow"
                direction = "临界偏高 ↗"
                reason = f"已达参考上限 {round(val_num / high * 100, 1)}%（上限 {high}）"
        elif mode == "lower":
            if val_num < low:
                risk_level = "red"
                direction = "偏低 ↓"
                reason = f"低于参考下限（{val_num} < {low}）"
            elif low > 0 and (val_num / low) <= 1.15:
                risk_level = "yellow"
                direction = "临界偏低 ↘"
                reason = f"接近参考下限（{val_num}，下限 {low}）"

    # 3. Clinical early-warning overrides (stricter than generic lab ranges, gender-aware)
    if val_num is not None and risk_level == "normal":
        if "糖化血红蛋白" in name and val_num >= 5.7:
            risk_level = "yellow"
            direction = "临床警戒 ↗"
            reason = f"糖化血红蛋白 {val_num}% 已达糖尿病前期国际警戒线（≥5.7%）"
        elif "葡萄糖(空腹)" in name and val_num >= 5.6:
            risk_level = "yellow"
            direction = "临床警戒 ↗"
            reason = f"空腹血糖 {val_num} mmol/L 已进入糖耐量关注区间（≥5.6）"
        elif "估算肾小球滤过率" in name and val_num < 90:
            risk_level = "yellow"
            direction = "临界关注 ↘"
            reason = f"eGFR {val_num} 略低于理想值 90，建议结合肌酐与尿检共同追踪"
        elif "尿酸" in name:
            if gender == "女":
                if val_num > 360:
                    risk_level = "red"
                    direction = "偏高 ↑"
                    reason = f"女性血尿酸 {val_num} μmol/L 超出临床警戒上限（>360）"
                elif val_num >= 320:
                    risk_level = "yellow"
                    direction = "临界关注 ↗"
                    reason = f"女性血尿酸 {val_num} μmol/L 逼近高尿酸警戒线（360）"
            elif val_num >= 380:
                risk_level = "yellow"
                direction = "临界关注 ↗"
                reason = f"血尿酸 {val_num} μmol/L 接近高尿酸警戒线"
        elif "血红蛋白" in name and "糖化" not in name and "平均" not in name and val_num > 30:
            if gender == "女" and val_num < 115:
                risk_level = "red"
                direction = "偏低 ↓"
                reason = f"女性血红蛋白 {val_num} g/L 低于参考下限（115）"
            elif gender == "男" and val_num < 120:
                risk_level = "red"
                direction = "偏低 ↓"
                reason = f"男性血红蛋白 {val_num} g/L 低于参考下限（120）"

    # 4. Explicit flag_text fallback
    if risk_level == "normal" and flag_text:
        ft = flag_text.upper()
        if any(k in ft for k in ("H", "↑", "高", "POS", "阳")):
            risk_level = "red"
            direction = "偏高 ↑"
            reason = f"原报告标注异常（{flag_text}）"
        elif any(k in ft for k in ("L", "↓", "低")):
            risk_level = "red"
            direction = "偏低 ↓"
            reason = f"原报告标注异常（{flag_text}）"

    if mode == "none" and not flag_text:
        risk_level = "info"

    return {
        "id": obs.get("id"),
        "report_date": obs.get("report_date", ""),
        "name": name,
        "loinc_code": obs.get("loinc_code", ""),
        "system": classify_system(name),
        "value_text": val_text,
        "value_num": val_num,
        "unit": unit,
        "ref_text": ref_text,
        "risk_level": risk_level,
        "direction": direction,
        "reason": reason,
        "range_pct": range_pct,
        "source_ref": obs.get("source_ref", ""),
    }


def load_food_therapy_rules_text(rules_path="rules/food_therapy_rules.yaml"):
    if os.path.exists(rules_path):
        with open(rules_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def mine_three_layer_risks(observations, medications=None, rules_path="rules/food_therapy_rules.yaml", user_profile=None):
    """Run the Three-Layer Proactive Risk Mining pipeline on Mirobody observations."""
    evaluated = [evaluate_observation(o, user_profile=user_profile) for o in observations]

    # Collect unique report dates and source files
    report_dates = sorted({e["report_date"] for e in evaluated if e["report_date"]})
    source_files = sorted({e["source_ref"] for e in evaluated if e["source_ref"]})

    # Build series across dates to detect cross-date trends
    series_map = defaultdict(list)
    for e in evaluated:
        # Distinguish blood vs urine creatinine by keeping name when unit differs
        key = (e["loinc_code"] + "|" + e["unit"]) if e["loinc_code"] else (e["name"] + "|" + e["unit"])
        series_map[key].append(e)

    trend_alerts = []
    for key, pts in series_map.items():
        pts_sorted = sorted(pts, key=lambda x: x["report_date"])
        num_pts = [p for p in pts_sorted if p["value_num"] is not None]
        if len(num_pts) >= 2 and num_pts[0]["report_date"] != num_pts[-1]["report_date"]:
            first, last = num_pts[0], num_pts[-1]
            if first["value_num"] != 0:
                pct_change = round((last["value_num"] - first["value_num"]) / abs(first["value_num"]) * 100, 1)
                if abs(pct_change) >= 10.0:
                    trend_alerts.append({
                        "name": last["name"],
                        "system": last["system"],
                        "from_date": first["report_date"],
                        "from_val": first["value_text"],
                        "to_date": last["report_date"],
                        "to_val": last["value_text"],
                        "unit": last["unit"],
                        "pct_change": pct_change,
                    })

    # Layer 1 & Layer 2 collections
    red_flags = [e for e in evaluated if e["risk_level"] == "red"]
    yellow_flags = [e for e in evaluated if e["risk_level"] == "yellow"]

    # Protective highlights (positive reinforcement)
    protective_highlights = []
    for e in evaluated:
        n, v = e["name"], e["value_num"]
        if v is None:
            if "正常心电图" in n or "正常心电图" in e["value_text"]:
                protective_highlights.append({"name": "心电图", "value": "窦性心律 / 正常心电图", "note": "心脏电生理节律稳健"})
            continue
        if "低密度脂蛋白" in n and v < 2.6:
            protective_highlights.append({"name": n, "value": f"{e['value_text']} {e['unit']}", "note": "动脉粥样硬化核心风险指标控制极佳"})
        elif "高密度脂蛋白" in n and v >= 1.2:
            protective_highlights.append({"name": n, "value": f"{e['value_text']} {e['unit']}", "note": "血管保护性胆固醇充裕"})
        elif "超敏C反应蛋白" in n and (v <= 1.0 or e["value_text"].startswith("<")):
            protective_highlights.append({"name": n, "value": f"{e['value_text']} {e['unit']}", "note": "全身慢性低度炎症水平极低"})
        elif "25-羟基维生素D" in n and v >= 75:
            protective_highlights.append({"name": n, "value": f"{e['value_text']} {e['unit']}", "note": "维生素D储备充足，利于免疫与骨骼代谢"})
        elif "尿白蛋白/肌酐" in n and v < 30:
            protective_highlights.append({"name": n, "value": f"{e['value_text']} {e['unit']}", "note": "肾小球滤过膜早期蛋白漏出阴性，属积极保护信号"})
        elif "肌钙蛋白" in n and v < 14:
            protective_highlights.append({"name": n, "value": f"{e['value_text']} {e['unit']}", "note": "心肌细胞无急性损伤信号"})

    # Group all items by medical system in a deterministic order
    system_order = [s[0] for s in SYSTEM_RULES] + ["其他检查项目"]
    grouped_systems = []
    by_sys = defaultdict(list)
    for e in evaluated:
        by_sys[e["system"]].append(e)

    for sys_name in system_order:
        items = by_sys.get(sys_name, [])
        if not items:
            continue
        red_cnt = sum(1 for i in items if i["risk_level"] == "red")
        yel_cnt = sum(1 for i in items if i["risk_level"] == "yellow")
        grouped_systems.append({
            "system": sys_name,
            "total_count": len(items),
            "red_count": red_cnt,
            "yellow_count": yel_cnt,
            "items": items,
        })

    return {
        "summary_stats": {
            "total_observations": len(evaluated),
            "report_dates": report_dates,
            "file_count": len(source_files),
            "red_count": len(red_flags),
            "yellow_count": len(yellow_flags),
            "trend_alert_count": len(trend_alerts),
        },
        "layer1_red_flags": red_flags,
        "layer2_yellow_flags": yellow_flags,
        "layer2_trend_alerts": trend_alerts,
        "protective_highlights": protective_highlights,
        "systems": grouped_systems,
        "medications": medications or [],
        "food_therapy_rules_yaml": load_food_therapy_rules_text(rules_path),
    }
