"""端到端编排器：脱敏 -> 跨年趋势分析 -> 红绿灯规则匹配 -> DeepSeek-R1 归因推理 -> 报告数据封装。"""

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .deepseek_client import DeepSeekClient, extract_json_block
from .deid import deidentify_payload
from .rule_engine import (
    analyze_trends,
    load_rules,
    match_food_therapy_rules,
    resolve_constitution_hints,
)


REASONER_SYSTEM_PROMPT = """你是一位兼具现代循证预防医学视角与传统药食同源食养智慧的健康管理顾问。
你的任务是基于【已脱敏的跨年体检趋势】、【用户干预事件锚点】、【5选体质软体感】以及【确定性药食同源红绿灯知识库】，输出一份温和、专业、克制、极易读懂的个人食养报告 JSON。

严格遵守以下合规与体验红线：
1. 严禁做出疾病确诊、处方用药调整建议或使用“根治/消除/包治”等医疗宣传违禁词。
2. 所有推荐食材必须严格限定在输入的红绿灯知识库（国家卫健委药食同源目录）范围内，并结合用户的体质软体感做温和微调（例如肠胃偏弱/畏寒者要提醒少寒凉）。
3. 先写“🔴 红灯避坑禁忌”建立买方信任，再写“🟢 绿灯温和食养搭配”，避免推销感。
4. 必须将“跨年指标拐点”与“干预事件锚点”对齐点评，指出哪些干预已见效、哪些临界指标正在悄悄上升。
5. 只输出合法 JSON，严格匹配要求的结构。
"""


def _build_reasoner_prompt(
    cleaned_data: Dict[str, Any],
    trends: Dict[str, Any],
    matched_rules: List[Dict[str, Any]],
    constitution_hints: List[Dict[str, str]],
    interventions: List[Dict[str, Any]],
) -> str:
    context = {
        "profile": cleaned_data.get("profile", {}),
        "report_dates": trends.get("report_dates", []),
        "indicators_summary": [
            {
                "code": i["code"],
                "name": i["name"],
                "unit": i["unit"],
                "ref_range": f"{i['ref_low']} ~ {i['ref_high']}",
                "status": i["status_label"],
                "history": [{"date": p["date"], "value": p["value"]} for p in i["points"]],
            }
            for i in trends.get("indicators", [])
        ],
        "latest_findings": trends.get("latest_findings", []),
        "interventions": interventions,
        "constitution_hints": constitution_hints,
        "matched_food_therapy_rules": [
            {
                "title": r["title"],
                "matched_reasons": r["matched_reasons"],
                "plain_translation": r["plain_translation"],
                "red_light_avoid": r["red_light_avoid"],
                "green_light_food_homology": r["green_light_food_homology"],
                "recheck_suggestion": r["recheck_suggestion"],
            }
            for r in matched_rules
        ],
    }

    schema_hint = """请输出严格符合以下字段的 JSON：
{
  "report_title": "跨年体检趋势与四季药食同源食养报告",
  "overall_badge": "如：代谢改善期 · 重点护糖控脂",
  "executive_summary": "100~140字的核心总览，用温暖人话点出最大亮点（干预改善）和最需要提前兜底的临界风险。",
  "intervention_insights": [
    "结合干预时间轴与指标拐点的具体归因点评（2~3条）"
  ],
  "plain_translations": [
    {
      "topic": "通俗主题名",
      "evidence": "对应具体指标或超声结论",
      "explanation": "60~90字把医学术语讲透的人话翻译"
    }
  ],
  "red_light_avoid": [
    {
      "title": "千万别乱踩的坑（简短标题）",
      "detail": "具体说明为何要避开（结合本人指标与体质）"
    }
  ],
  "green_light_plan": [
    {
      "scene": "如：午后解腻代谢茶 / 晚餐主食替补 / 日常舒缓养护",
      "ingredients": "药食同源食材组合",
      "why_fit": "结合指标与体质说明为什么温和适合",
      "caution": "基于体质的细微注意事项"
    }
  ],
  "recheck_countdown": {
    "days": 90,
    "target_date": "YYYY-MM-DD",
    "items": ["建议复查项目1", "建议复查项目2"],
    "tip": "一句话复查提醒"
  }
}"""

    return f"以下是脱敏后的综合健康上下文：\n```json\n{json.dumps(context, ensure_ascii=False, indent=2)}\n```\n\n{schema_hint}"


def _build_offline_synthesis(
    trends: Dict[str, Any],
    matched_rules: List[Dict[str, Any]],
    constitution_hints: List[Dict[str, str]],
    interventions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """离线/演示模式：基于确定性规则引擎生成高质量结构化报告内容，零 API 成本秒出成品。"""
    indicators = trends.get("indicators", [])
    high_items = [i for i in indicators if i["status"] in ("high", "low")]
    borderline_items = [i for i in indicators if i["status"] == "borderline_worsening"]
    improving_items = [i for i in indicators if i["status"] == "improving"]

    # 构造核心总览
    parts = []
    if improving_items:
        names = "、".join(i["name"] for i in improving_items[:2])
        parts.append(f"近一年你的{names}已出现明确回落改善，说明此前的作息与饮食微调真实见效")
    if high_items:
        names = "、".join(f"{i['name']}({i['latest_value']}{i['unit']})" for i in high_items[:2])
        parts.append(f"当前{names}仍略高于参考上限，是下一阶段稳态调理的核心焦点")
    if borderline_items:
        names = "、".join(f"{i['name']}({i['latest_value']}{i['unit']})" for i in borderline_items[:2])
        parts.append(f"特别提醒：{names}虽然仍在体检单正常范围内，但已连续跨年单边爬升，建议趁早用温和食养把趋势压平")
    if not parts:
        parts.append("整体核心代谢指标处于稳态区间，建议继续保持规律作息与四季温和食养，定期年度随访对比。")

    # 干预归因
    insights: List[str] = []
    if interventions and improving_items:
        latest_iv = interventions[-1]
        imp_desc = "、".join(
            f"{i['name']}由 {i['points'][-2]['value']} 降至 {i['latest_value']} {i['unit']}"
            for i in improving_items[:2]
        )
        insights.append(
            f"「{latest_iv['date']} {latest_iv['title']}」与指标拐点高度吻合：{imp_desc}，验证了温和生活方式干预的有效性。"
        )
    if high_items:
        h = high_items[0]
        if len(h["points"]) >= 2 and h["latest_value"] < h["points"][-2]["value"]:
            insights.append(
                f"{h['name']}已从峰值 {h['points'][-2]['value']} 回落至 {h['latest_value']} {h['unit']}，距离达标线（{h['ref_high']}）仅差一步，继续稳住晚餐油脂与碳水即可望回正。"
            )
    if borderline_items:
        b = borderline_items[0]
        seq = " → ".join(str(p["value"]) for p in b["points"])
        insights.append(
            f"{b['name']}连续呈现单边上行轨迹（{seq} {b['unit']}），虽未触发医院标红，但结合餐后困倦体感，提示胰岛素敏感性需提前养护。"
        )
    if not insights:
        insights.append("已记录历年体检基线数据，建议在每次调整作息、饮食或茶饮时打上“干预锚点”，下次复查即可量化对比效果。")

    # 人话翻译
    plain_translations = []
    for r in matched_rules:
        plain_translations.append(
            {
                "topic": r["title"],
                "evidence": "；".join(r["matched_reasons"][:2]),
                "explanation": r["plain_translation"],
            }
        )
    if not plain_translations:
        plain_translations.append(
            {
                "topic": "基础代谢稳态良好",
                "evidence": "本次核心生化指标均在参考区间内",
                "explanation": "未见明显代谢失衡信号，日常顺应季节饮食、保持规律运动与睡眠即可。",
            }
        )

    # 红灯避坑
    red_light_avoid = []
    seen_red = set()
    for r in matched_rules:
        for item in r.get("red_light_avoid", []):
            if item not in seen_red:
                seen_red.add(item)
                red_light_avoid.append(
                    {
                        "title": r["title"].split("（")[0] + " · 避坑提醒",
                        "detail": item,
                    }
                )
    red_light_avoid = red_light_avoid[:5]

    # 体质微调提示
    const_note = (
        "结合你勾选的「" + "、".join(c["label"] for c in constitution_hints) + "」体感，方案已优先避开过度温燥滋补与高糖膏方。"
        if constitution_hints
        else "建议饮用前留意肠胃耐受度，温热少量多次饮用。"
    )

    # 绿灯食养
    green_light_plan = []
    for r in matched_rules:
        for g in r.get("green_light_food_homology", []):
            green_light_plan.append(
                {
                    "scene": r["title"].split("（")[0],
                    "ingredients": g["ingredients"],
                    "why_fit": g["role"],
                    "caution": g["usage_tip"],
                }
            )
    green_light_plan = green_light_plan[:4]

    target_date = (datetime.date.today() + datetime.timedelta(days=90)).isoformat()
    recheck_items = [r["recheck_suggestion"] for r in matched_rules[:3]] or ["年度常规体检复查"]

    badge = "代谢改善期 · 临界早防" if (improving_items and (high_items or borderline_items)) else (
        "重点代谢调理期" if (high_items or borderline_items) else "健康稳态养护期"
    )

    return {
        "report_title": "跨年体检趋势 × 药食同源食养报告",
        "overall_badge": badge,
        "executive_summary": "；".join(parts) + "。" + const_note,
        "intervention_insights": insights,
        "plain_translations": plain_translations,
        "red_light_avoid": red_light_avoid,
        "green_light_plan": green_light_plan,
        "recheck_countdown": {
            "days": 90,
            "target_date": target_date,
            "items": recheck_items,
            "tip": "建议保持本次食养与作息节奏满 1 个代谢周期（90 天）后在同一机构复查，对比趋势更有参考价值。",
        },
    }


def run_pipeline(
    raw_data: Dict[str, Any],
    rules_path: Path,
    interventions_path: Optional[Path] = None,
    client: Optional[DeepSeekClient] = None,
    use_ai_reasoner: bool = True,
    constitution_override: Optional[List[str]] = None,
    interventions_override: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """执行完整分析与食养报告生成管线（数据脱敏 -> 趋势分析 -> 规则匹配 -> 推理合成）。"""
    rules_config = load_rules(rules_path)
    cleaned_data = deidentify_payload(raw_data)

    if constitution_override is not None:
        cleaned_data["constitution_selected"] = constitution_override

    interventions: List[Dict[str, Any]] = []
    if interventions_override is not None:
        interventions = interventions_override
    elif interventions_path and interventions_path.exists():
        interventions = json.loads(interventions_path.read_text(encoding="utf-8")).get("interventions", [])

    trends = analyze_trends(cleaned_data.get("reports", []))
    matched_rules = match_food_therapy_rules(trends, cleaned_data.get("profile", {}), rules_config)
    constitution_hints = resolve_constitution_hints(
        cleaned_data.get("constitution_selected", []),
        rules_config,
    )

    ai_mode = "offline_rule_engine"
    if use_ai_reasoner and client and client.is_configured():
        print(f"[深度推理] 正在调用 {client.reasoner_model} 生成跨年归因与个性化食养方案...")
        user_prompt = _build_reasoner_prompt(
            cleaned_data=cleaned_data,
            trends=trends,
            matched_rules=matched_rules,
            constitution_hints=constitution_hints,
            interventions=interventions,
        )
        raw_resp = client.chat(
            messages=[
                {"role": "system", "content": REASONER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=client.reasoner_model,
            temperature=None,
            max_tokens=4096,
        )
        synthesis = extract_json_block(raw_resp)
        ai_mode = client.reasoner_model
    else:
        synthesis = _build_offline_synthesis(
            trends=trends,
            matched_rules=matched_rules,
            constitution_hints=constitution_hints,
            interventions=interventions,
        )

    return {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ai_mode": ai_mode,
        "compliance_note": rules_config.get("compliance_note", ""),
        "profile": cleaned_data.get("profile", {}),
        "constitution_hints": constitution_hints,
        "interventions": interventions,
        "trends": trends,
        "matched_rules": matched_rules,
        "synthesis": synthesis,
    }
