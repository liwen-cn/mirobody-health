"""Proactive Three-Layer Health Risk & Food-Therapy Reasoning Engine powered by DeepSeek-Flash."""

import json
import re
from src.api_client import call_deepseek_flash


SYSTEM_PROMPT = """你是一位兼具现代临床预防医学、代谢病学与传统药食同源滋补养生（燕窝、参类/虫草、阿胶/膏滋、药食同源茶饮）的资深健康管理专家。
你的服务对象是不懂医疗术语的普通人（家庭成员或私域健康管理客户）——他们面对体检报告不知道该问什么，你需要主动帮他们把隐藏在数据里的风险痛点挖出来，用“专业但不制造恐慌、透彻又听得懂”的中文讲清楚，并给出“先排雷避坑、再温和食养、最后复查验证”的可执行方案。

严格准则：
1. 严禁编造任何未在输入数据中出现的指标数值、日期或检查项；所有引用数字必须与输入完全一致。
2. 严格遵守医疗合规红线：不做临床确诊、不开具处方药，明确区分“日常膳食与生活方式调理”与“需前往医院复查确认”。
3. 所有推荐的药食同源食材必须属于国家卫健委《按照传统既是食品又是中药材的物质目录》范畴。
4. 必须严格结合用户的性别、年龄及近期用药/调理备注来校准风险权重、复查科室与药食同源禁忌（例如男女参考阈值差异、女性备孕/孕期/围绝经期禁忌、高龄人群脾胃负荷及抗凝/降糖/降压药与食材交互）；若用户填写了近期用药或调理备注，必须在痛点解读或食养避坑中明确呼应。
5. 全篇通俗化与参考区间铁律：面向非医学背景读者写作，禁止在一句话里堆砌多个裸专业名词或裸数字。在整份报告（含 executive_summary、protective_highlights、wearable_insights、core_pain_points、food_therapy_plan、doctor_questions）中，任何医学专业名词、化验项目名或英文缩写（如 LDL、sdLDL、HbA1c、CA19-9、CA242、低级别上皮内瘤变、腔隙性缺血灶、全血高切粘度、胃蛋白酶原Ⅰ 等）首次出现时，必须紧跟括号用大白话说明“它是干什么的/查什么的”；凡引用数值型化验指标，必须同时给出输入数据 `ref` 字段中的正常参考区间（若输入未附参考区间，严禁自行编造，须注明“影像/病理提示”或“报告未附区间”）。
6. 必须严格返回合法的 JSON 对象，不要附加任何 JSON 之外的文字。"""


USER_PROMPT_TEMPLATE = """请基于以下由 Mirobody 标准化底座提取、并经“三层主动风险挖掘引擎”预筛后的用户体检数据，生成一份深度《AI 主动健康风险挖掘与四季食养报告》JSON。

【用户基础画像与体感标签（脱敏）】
{profile_json}

【三层主动风险挖掘预筛结果】
- 统计概览：{stats_json}
- 第一层 · 显性异常红牌（超参考区间/异常定性）：
{red_json}
- 第二层 · 隐性恶化/临界黄牌（逼近上限/临床早筛警戒）：
{yellow_json}
- 第二层 · 跨期趋势预警（若有）：
{trend_json}
- 保护性健康亮点（正向锚点）：
{protective_json}
- 分系统全量指标摘要：
{systems_json}
- 已记录的用药/干预（若有）：
{meds_json}
- Apple Watch / 穿戴设备长期行为趋势（若有；务必留意每项指标的样本天数 days，样本少于 7 天的短窗口切勿过度解读，应优先采信近 1 年 / 近 3 年及跨年趋势）：
{wearable_json}

【药食同源红绿灯知识库（YAML 规则参考）】
{rules_yaml}

请严格按以下 JSON Schema 输出（所有字段必填）：
{{
  "report_title": "报告主标题（简洁有质感，如：深度体检风险洞察与四季食养方案）",
  "overall_grade": "健康风险总评等级，四选一：稳健优选 / 轻度预警 / 重点干预 / 建议尽快就医复查",
  "executive_summary": {{
    "one_line_verdict": "30字以内的一句话总体大白话定性（不堆术语，先给读者心理有底的整体判断）",
    "good_news": {{
      "summary": "1-2句大白话讲清1-2个最让人安心的底子亮点（先说哪里好，不堆生僻英文缩写）",
      "metrics": [
        {{
          "plain_name": "大白话叫法（如：坏胆固醇 / 近3个月平均血糖 / 肾脏早期漏蛋白）",
          "term": "体检单原名（如：低密度脂蛋白 / 糖化血红蛋白）",
          "value": "实测值及单位（须与输入完全一致，如：2.18 mmol/L 或 5.8% → 5.4%）",
          "ref": "正常参考区间（须来自输入 ref，如：正常 0.00—3.12 或 正常 4.0—6.0%）",
          "status": "4-8字大白话结论（如：很理想 / 明显好转 / 正常安心）"
        }}
      ]
    }},
    "watch_items": [
      {{
        "title": "普通人一眼看懂的关注点标题（2-3条，如：胃肠息肉防复发与慢性炎症）",
        "severity": "red 或 yellow",
        "plain_explain": "1-2句大白话讲清发生了什么、为什么要管（首次出现的医学名词必须括号附白话解释，客观不恐吓）",
        "metrics": [
          {{
            "plain_name": "大白话说明（如：消化道相关参考指标 / 血液粘稠度）",
            "term": "体检单原名（如：CA19-9 / 全血高切粘度）",
            "value": "实测值及单位（须与输入一致）",
            "ref": "正常参考区间（须来自输入 ref；影像/病理类无区间时写“影像/病理提示”）",
            "status": "4-8字状态判断（如：虽降仍偏高 / 贴近上限）"
          }}
        ]
      }}
    ],
    "first_step": "1-2句具体且最省力的第一步行动建议（明确先挂什么科查什么、日常先落哪一件小事）"
  }},
  "protective_highlights": [
    {{
      "title": "亮点名称（如：坏胆固醇控制极佳）",
      "evidence": "具体数值、单位及来自输入 ref 的正常参考区间（如：低密度脂蛋白胆固醇 2.18 mmol/L，正常参考 0.00—3.12 mmol/L）",
      "meaning": "用一句大白话说明它查的是什么、代表什么好消息"
    }}
  ],
  "wearable_insights": {{
    "headline": "若输入包含 Apple Watch 穿戴数据，用一句话概括穿戴趋势与体检的交叉印证结论；若无穿戴数据请将整个 wearable_insights 设为 null",
    "highlights": ["穿戴呈现的正向行为证据（带跨年或窗口数值）"],
    "warnings": ["穿戴暴露出的隐性作息/恢复短板（带跨年或窗口数值，避开样本极少的短窗口）"],
    "lab_cross_check": "70-110字：将 Apple Watch 客观行为趋势（睡眠、静息心率、HRV、步数/锻炼、体重）与本次体检化验单核心痛点交叉印证，讲清背后的因果关联。",
    "action_focus": "一句话突出给出当下最省力的穿戴/生活行动抓手（如：先把日均睡眠拉回 7 小时，比盲目加练更划算）"
  }},
  "core_pain_points": [
    {{
      "priority": 1,
      "severity": "red 或 yellow",
      "title": "跨系统联动痛点标题（普通人一眼看懂）",
      "linked_indicators": ["大白话短标签｜体检单原名 实测值 单位（正常参考：输入 ref 或 影像/病理提示）"],
      "plain_why": "医生没空细讲的大白话拆解（90-140字）：首次出现的任何医学名词或英文缩写必须括号附一句白话解释，带出对应正常参考区间；讲清这些指标串联在一起说明身体发生了什么、为什么只看单项容易被骗",
      "risk_if_ignored": "如果放任不管，未来1-3年可能演变成什么问题（客观理性，不恐吓）",
      "action_focus": "当下最优先的1-2个抓手（饮食/作息/复查）"
    }}
  ],
  "system_analyses": [
    {{
      "system_name": "系统名称（覆盖所有已检核心系统，通常5-6个）",
      "status": "red / yellow / green",
      "headline": "15-25字一句话定性结论（高度精炼，不展开长段落复述；红黄牌细节已在第一部分展开）"
    }}
  ],
  "food_therapy_plan": [
    {{
      "category_name": "品类名称（必须覆盖：1. 燕窝与滋阴类、2. 参类与虫草补气类、3. 阿胶与膏滋厚味类、4. 药食同源日常茶饮）",
      "badge_type": "red（阶段性慎用/避坑）或 yellow（有条件精选）或 green（重点推荐）",
      "status_label": "简短标签，如：阶段性禁用高糖款 / 温和清补可用 / 重点推荐日常疏通",
      "red_light_avoid": "结合该用户的具体异常/临界指标，明确哪些吃法、配料或品类会加重负担并讲清原因（直接写正文，不要以‘【先排雷...】’开头）。",
      "green_light_recommend": "给出具体药食同源食材、无糖/清炖做法、饮用时机与温和频次（直接写正文，不要以‘【可安心用...】’开头）。"
    }}
  ],
  "doctor_questions": [
    {{
      "department": "建议挂号/咨询科室（如：内分泌科 / 肾内科 / 全科体检复查）",
      "question": "普通人可以直接照着念给医生听的精准提问（兼顾大白话与具体数值、正常参考区间）",
      "why_ask": "为什么要问这个问题（用通俗语言帮用户听懂背后的排查目的）"
    }}
  ],
  "recheck_timeline": [
    {{
      "timeframe": "时间节点（如：1-2周内复核 / 60-90天后复查）",
      "items": "建议复查的具体项目（尽量注明社区医院/三甲均可的低成本单项）",
      "goal": "复查想验证的目标"
    }}
  ],
  "disclaimer": "合规免责声明（明确本报告基于已上传体检数据整理，仅作健康风险科普、日常膳食滋补与复查沟通参考，不构成医疗诊断、处方或用药依据；异常指标请遵医嘱进一步检查。）"
}}
"""


def _compact_items(items):
    return [
        {
            "date": i["report_date"],
            "name": i["name"],
            "val": f"{i['value_text']} {i['unit']}".strip(),
            "ref": i["ref_text"],
            "level": i["risk_level"],
            "dir": i["direction"],
            "reason": i["reason"],
        }
        for i in items
    ]


def generate_proactive_report_json(mined_data, api_key, user_profile=None, wearable_summary=None):
    """Call DeepSeek-Flash to synthesize the proactive 3-layer risk & food-therapy report."""
    profile = user_profile or {
        "code_name": "家庭健康档案",
        "constitution_tags": [],
        "notes": "未额外填写主观体感，请完全基于客观体检指标分析",
    }

    compact_systems = []
    for sys_block in mined_data["systems"]:
        # Keep all red/yellow items + up to 8 representative normal items per system so multi-year payloads stay crisp
        flagged = [i for i in sys_block["items"] if i["risk_level"] in ("red", "yellow")]
        normals = [i for i in sys_block["items"] if i["risk_level"] not in ("red", "yellow")]
        selected = flagged + normals[-8:]
        compact_systems.append({
            "system": sys_block["system"],
            "total_count": sys_block["total_count"],
            "red_count": sys_block["red_count"],
            "yellow_count": sys_block["yellow_count"],
            "key_items": _compact_items(selected),
        })

    prompt = USER_PROMPT_TEMPLATE.format(
        profile_json=json.dumps(profile, ensure_ascii=False),
        stats_json=json.dumps(mined_data["summary_stats"], ensure_ascii=False),
        red_json=json.dumps(_compact_items(mined_data["layer1_red_flags"][:40]), ensure_ascii=False, indent=2),
        yellow_json=json.dumps(_compact_items(mined_data["layer2_yellow_flags"][:30]), ensure_ascii=False, indent=2),
        trend_json=json.dumps(mined_data["layer2_trend_alerts"][:30], ensure_ascii=False, indent=2),
        protective_json=json.dumps(mined_data["protective_highlights"][:12], ensure_ascii=False, indent=2),
        systems_json=json.dumps(compact_systems, ensure_ascii=False, indent=2),
        meds_json=json.dumps(mined_data["medications"], ensure_ascii=False),
        wearable_json=json.dumps(wearable_summary, ensure_ascii=False, indent=2) if (wearable_summary and wearable_summary.get("has_data")) else "（暂无穿戴设备数据）",
        rules_yaml=mined_data["food_therapy_rules_yaml"] or "（无外部规则文件）",
    )

    raw_content = call_deepseek_flash(
        prompt=prompt,
        api_key=api_key,
        system_prompt=SYSTEM_PROMPT,
        json_mode=True,
        max_tokens=16384,
        timeout=240,
    )

    m = re.search(r"```json\s*(.*?)\s*```", raw_content, re.DOTALL)
    json_str = m.group(1) if m else raw_content.strip()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Fallback retry with thinking disabled for guaranteed complete JSON output
        raw_retry = call_deepseek_flash(
            prompt=prompt,
            api_key=api_key,
            system_prompt=SYSTEM_PROMPT,
            json_mode=True,
            max_tokens=16384,
            timeout=240,
            disable_thinking=True,
        )
        m2 = re.search(r"```json\s*(.*?)\s*```", raw_retry, re.DOTALL)
        json_str2 = m2.group(1) if m2 else raw_retry.strip()
        return json.loads(json_str2)
