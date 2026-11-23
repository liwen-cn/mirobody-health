"""Zero-dependency de-identified demo dataset & offline report payload for `--demo` mode.

Allows users to preview the full Three-Layer Proactive Risk Miner, Apple Watch
cross-check SVG trends, food-therapy traffic-light plan, and responsive HTML
report in 1 second without Docker, Mirobody PostgreSQL, or an API key.
"""

import json
import os


DEFAULT_MOCK_PATH = os.path.join("food_therapy_demo", "data", "mock_checkups.json")


def load_demo_profile():
    """Return a strictly synthetic, de-identified user profile for demo runs."""
    return {
        "code_name": "林先生（演示样本）",
        "gender": "男",
        "age": 36,
        "constitution_tags": ["餐后易困乏力", "口苦易上火"],
        "recent_note": "2026年5月起晚间戒夜宵 + 每周3次快走 + 午后饮用葛根陈皮山楂茶",
    }


def load_demo_observations(mock_path=DEFAULT_MOCK_PATH):
    """Load synthetic 3-year checkup JSON and convert it to Mirobody `v_observation` schema."""
    with open(mock_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    observations = []
    obs_id = 90001
    for rep in data.get("reports", []):
        report_date = rep.get("report_date", "")
        source_file = rep.get("source_file", "demo_checkup.pdf")
        source_ref = f"demo_uploads/{source_file}"

        for ind in rep.get("indicators", []):
            low = ind.get("ref_low")
            high = ind.get("ref_high")
            ref_text = f"{low}--{high}" if (low is not None and high is not None) else ""
            val = ind.get("value")
            unit = ind.get("unit", "")
            name = ind.get("name", "")
            code = ind.get("code", "")

            observations.append({
                "id": obs_id,
                "report_date": report_date,
                "name_text": name,
                "display_zh": name,
                "display_en": code,
                "value_text": str(val),
                "value_num": float(val) if isinstance(val, (int, float)) else None,
                "value_canonical": str(val),
                "unit_text": unit,
                "unit_canonical": unit,
                "ref_text": ref_text,
                "ref_low": low,
                "ref_high": high,
                "flag_text": "",
                "loinc_code": f"DEMO-{code}" if code else "",
                "panel_text": "年度综合体检（演示样本）",
                "specimen_text": "静脉血",
                "kind": "lab",
                "value_kind": "numeric",
                "source_ref": source_ref,
            })
            obs_id += 1

        for finding in rep.get("findings", []):
            section = finding.get("section", "超声检查")
            summary = finding.get("summary", "")
            observations.append({
                "id": obs_id,
                "report_date": report_date,
                "name_text": section,
                "display_zh": section,
                "display_en": "",
                "value_text": summary,
                "value_num": None,
                "value_canonical": "",
                "unit_text": "",
                "unit_canonical": "",
                "ref_text": "阴性（未见异常）",
                "ref_low": None,
                "ref_high": None,
                "flag_text": "",
                "loinc_code": "",
                "panel_text": "影像检查（演示样本）",
                "specimen_text": "",
                "kind": "imaging",
                "value_kind": "text",
                "source_ref": source_ref,
            })
            obs_id += 1

    # Add synthetic protective baseline markers on the latest report date
    protective_extras = [
        ("高密度脂蛋白胆固醇", "HDL-C", 1.38, "mmol/L", 1.04, 1.55, "静脉血"),
        ("超敏C反应蛋白", "hs-CRP", 0.45, "mg/L", 0.0, 3.0, "静脉血"),
        ("心电图", "ECG", "窦性心律 / 正常心电图", "", None, None, ""),
    ]
    latest_date = (data.get("reports") or [{}])[-1].get("report_date", "2026-10-15")
    latest_source = f"demo_uploads/{(data.get('reports') or [{}])[-1].get('source_file', '2026_checkup.pdf')}"
    for name, code, val, unit, low, high, specimen in protective_extras:
        is_num = isinstance(val, (int, float))
        observations.append({
            "id": obs_id,
            "report_date": latest_date,
            "name_text": name,
            "display_zh": name,
            "display_en": code,
            "value_text": str(val),
            "value_num": float(val) if is_num else None,
            "value_canonical": str(val),
            "unit_text": unit,
            "unit_canonical": unit,
            "ref_text": f"{low}--{high}" if is_num else "正常心电图",
            "ref_low": low,
            "ref_high": high,
            "flag_text": "",
            "loinc_code": f"DEMO-{code}",
            "panel_text": "年度综合体检（演示样本）",
            "specimen_text": specimen,
            "kind": "lab" if is_num else "ecg",
            "value_kind": "numeric" if is_num else "text",
            "source_ref": latest_source,
        })
        obs_id += 1

    return observations


def load_demo_wearable_summary():
    """Return a synthetic 3-year Apple Watch summary matching `fetch_wearable_summary()` schema."""
    return {
        "has_data": True,
        "source": "Apple Watch / Apple Health（演示样本）",
        "date_span": {
            "first_day": "2024-01-01",
            "last_day": "2026-10-15",
            "total_days": 962,
        },
        "metrics": [
            {
                "key": "dailyTotalSteps",
                "label": "日均步数",
                "unit": "步",
                "latest_val": 8420,
                "latest_date": "2026-10-15",
                "d30": {"avg": 8150, "days": 30},
                "d90": {"avg": 7860, "days": 90},
                "y1": {"avg": 7420, "days": 342},
                "y3": {"avg": 6480, "days": 962},
            },
            {
                "key": "dailyTotalExerciseMinutes",
                "label": "日均锻炼时长",
                "unit": "分钟",
                "latest_val": 36.0,
                "latest_date": "2026-10-15",
                "d30": {"avg": 34.5, "days": 30},
                "d90": {"avg": 32.0, "days": 90},
                "y1": {"avg": 29.4, "days": 340},
                "y3": {"avg": 22.8, "days": 950},
            },
            {
                "key": "dailyTotalSleepAnalysis_Asleep(Total)",
                "label": "日均总睡眠",
                "unit": "小时",
                "latest_val": 6.65,
                "latest_date": "2026-10-15",
                "d30": {"avg": 6.58, "days": 29},
                "d90": {"avg": 6.45, "days": 86},
                "y1": {"avg": 6.32, "days": 330},
                "y3": {"avg": 6.48, "days": 920},
            },
            {
                "key": "dailyAvgRestingHeartRates",
                "label": "日均静息心率",
                "unit": "bpm",
                "latest_val": 64.0,
                "latest_date": "2026-10-15",
                "d30": {"avg": 64.5, "days": 30},
                "d90": {"avg": 65.2, "days": 90},
                "y1": {"avg": 66.8, "days": 340},
                "y3": {"avg": 68.5, "days": 955},
            },
            {
                "key": "dailyAvgHrvSDNN",
                "label": "心率变异性 HRV",
                "unit": "ms",
                "latest_val": 44.2,
                "latest_date": "2026-10-15",
                "d30": {"avg": 43.0, "days": 30},
                "d90": {"avg": 41.8, "days": 90},
                "y1": {"avg": 39.6, "days": 336},
                "y3": {"avg": 37.9, "days": 940},
            },
            {
                "key": "dailyLastBodyMasss",
                "label": "体重",
                "unit": "kg",
                "latest_val": 74.8,
                "latest_date": "2026-10-15",
                "d30": {"avg": 75.0, "days": 24},
                "d90": {"avg": 75.6, "days": 68},
                "y1": {"avg": 76.9, "days": 260},
                "y3": {"avg": 77.5, "days": 710},
            },
        ],
        "yearly_trend": {
            "2024": {
                "日均步数": {"avg": 5980, "unit": "步", "days": 320},
                "日均锻炼时长": {"avg": 18.5, "unit": "分钟", "days": 315},
                "日均总睡眠": {"avg": 6.62, "unit": "小时", "days": 302},
                "日均静息心率": {"avg": 69.8, "unit": "bpm", "days": 318},
                "心率变异性 HRV": {"avg": 37.2, "unit": "ms", "days": 310},
                "体重": {"avg": 77.2, "unit": "kg", "days": 210},
            },
            "2025": {
                "日均步数": {"avg": 5420, "unit": "步", "days": 340},
                "日均锻炼时长": {"avg": 16.0, "unit": "分钟", "days": 335},
                "日均总睡眠": {"avg": 6.18, "unit": "小时", "days": 324},
                "日均静息心率": {"avg": 71.2, "unit": "bpm", "days": 338},
                "心率变异性 HRV": {"avg": 35.4, "unit": "ms", "days": 328},
                "体重": {"avg": 78.6, "unit": "kg", "days": 240},
            },
            "2026": {
                "日均步数": {"avg": 7860, "unit": "步", "days": 288},
                "日均锻炼时长": {"avg": 32.0, "unit": "分钟", "days": 286},
                "日均总睡眠": {"avg": 6.45, "unit": "小时", "days": 276},
                "日均静息心率": {"avg": 65.2, "unit": "bpm", "days": 288},
                "心率变异性 HRV": {"avg": 41.8, "unit": "ms", "days": 284},
                "体重": {"avg": 75.4, "unit": "kg", "days": 230},
            },
        },
    }


def get_offline_demo_report_json():
    """Return a pre-synthesized report JSON grounded strictly in the synthetic demo dataset."""
    return {
        "report_title": "深度体检风险洞察与四季食养方案（演示样本）",
        "overall_grade": "轻度预警",
        "executive_summary": {
            "one_line_verdict": "血脂与脂肪肝已在回落好转，眼下唯独空腹血糖还在悄悄贴近上限。",
            "good_news": {
                "summary": "2026年5月开始戒夜宵与快走确实见效了！血脂、尿酸、肝酶和超声脂肪肝全部比2025年回落，且全身炎症水平和血管好胆固醇很理想。",
                "metrics": [
                    {
                        "plain_name": "好胆固醇（血管清道夫）",
                        "term": "高密度脂蛋白胆固醇",
                        "value": "1.38 mmol/L",
                        "ref": "1.04—1.55 mmol/L",
                        "status": "底子充裕",
                    },
                    {
                        "plain_name": "全身隐性炎症指标",
                        "term": "超敏C反应蛋白",
                        "value": "0.45 mg/L",
                        "ref": "0.0—3.0 mg/L",
                        "status": "炎症极低",
                    },
                ],
            },
            "watch_items": [
                {
                    "title": "空腹血糖连续三年爬坡，已贴近正常上限",
                    "severity": "yellow",
                    "plain_explain": "空腹血糖（隔夜没吃早饭时的基础血糖）虽还没标红箭头，但从2024年一路走到5.96，离6.1的上限只差一步，说明身体对碳水的消化吸收效率在变慢。",
                    "metrics": [
                        {
                            "plain_name": "隔夜基础血糖",
                            "term": "空腹血糖",
                            "value": "5.96 mmol/L",
                            "ref": "3.9—6.1 mmol/L",
                            "status": "三年连涨贴上限",
                        },
                        {
                            "plain_name": "近2—3个月平均血糖",
                            "term": "糖化血红蛋白 (HbA1c)",
                            "value": "建议下次补查",
                            "ref": "常规参考 4.0—6.0%",
                            "status": "待补充验证",
                        },
                    ],
                },
                {
                    "title": "甘油三酯仍略超标，伴随轻度脂肪肝与甲状腺小结节随访",
                    "severity": "red",
                    "plain_explain": "甘油三酯（血液里最受夜宵、油腻饮食和甜饮影响的短期油脂）已从2025年的2.38降到1.88，但仍略高于1.7上限；甲状腺TI-RADS 3类小结节（良性概率极高的常见小囊泡/结节，约3.2mm）三年无变化，按期超声随访即可。",
                    "metrics": [
                        {
                            "plain_name": "血液短期油脂负荷",
                            "term": "甘油三酯",
                            "value": "1.88 mmol/L",
                            "ref": "0.4—1.7 mmol/L",
                            "status": "已明显回落仍微高",
                        },
                        {
                            "plain_name": "血尿酸（嘌呤代谢产物）",
                            "term": "血尿酸",
                            "value": "412 μmol/L",
                            "ref": "208—428 μmol/L",
                            "status": "虽降回正常仍贴上限",
                        },
                    ],
                },
            ],
            "first_step": "先把手头那份还没查的「糖化血红蛋白 + 餐后2小时血糖」抽空去社区或医院全科补测一下；日常保持戒夜宵，把睡眠从6.45小时往前拉半小时。",
        },
        "protective_highlights": [
            {
                "title": "血管保护性胆固醇充足",
                "evidence": "高密度脂蛋白胆固醇 1.38 mmol/L（正常参考 1.04—1.55 mmol/L）",
                "meaning": "俗称「好胆固醇」，负责把血管壁多余脂质搬回肝脏代谢，数值越高越能帮心血管兜底。",
            },
            {
                "title": "全身慢性低度炎症极低",
                "evidence": "超敏C反应蛋白 0.45 mg/L（正常参考 0.0—3.0 mg/L）",
                "meaning": "反映身体内部血管和组织有没有长期暗火发炎的灵敏指针，目前非常干净平稳。",
            },
            {
                "title": "心脏基础节律稳健",
                "evidence": "心电图：窦性心律 / 正常心电图（正常参考：正常心电图）",
                "meaning": "代表心脏跳动节律与心肌电传导正常，支撑您每周三次快走的有氧底子很安全。",
            },
        ],
        "wearable_insights": {
            "headline": "2026年重启快走与戒夜宵后，Apple Watch 的步数、静息心率与 HRV 全部同步转向正向，与血脂回落完全互证。",
            "highlights": [
                "日均步数从 2025 年低谷 5,420 步反弹至 2026 年 7,860 步（+45%），日均锻炼翻倍至 32 分钟。",
                "日均静息心率从 2025 年 71.2 bpm 稳步降至 2026 年 65.2 bpm，心率变异性 HRV（自主神经恢复弹性）回升至 41.8 ms，体重减重超 3 kg。",
            ],
            "warnings": [
                "2026 年日均总睡眠仅 6.45 小时，仍低于成人代谢修复建议线（7 小时），会直接拖慢夜间胰岛素敏感性修复。",
            ],
            "lab_cross_check": "2025 年穿戴记录的久坐与睡眠跌至 6.18 小时，恰好对应当年甘油三酯 2.38、尿酸 446、LDL-C 3.52 的全线飙红；2026 年 5 月起运动翻倍且减重后，血脂与脂肪肝随即改善，唯独睡眠不足仍在拖累空腹血糖缓慢抬升。",
            "action_focus": "不要盲目再加运动强度，先把每晚入睡时间固定提前 30 分钟（凑满 7 小时），对压低空腹血糖最划算。",
        },
        "core_pain_points": [
            {
                "priority": 1,
                "severity": "yellow",
                "title": "糖脂代谢负荷轴：血脂在回落，但空腹血糖连涨三年逼近红线",
                "linked_indicators": [
                    "隔夜基础血糖｜空腹血糖 5.96 mmol/L（正常参考：3.9—6.1）",
                    "短期油脂负荷｜甘油三酯 1.88 mmol/L（正常参考：0.4—1.7）",
                    "坏胆固醇｜低密度脂蛋白胆固醇 3.28 mmol/L（正常参考：0.0—3.4）",
                    "肝酶灵敏信号｜γ-谷氨酰转肽酶 46 U/L（正常参考：10—60）",
                    "影像提示｜腹部超声：轻度脂肪肝（较前略有减轻）",
                ],
                "plain_why": "甘油三酯（血液短期油脂）和 γ-谷氨酰转肽酶（反映肝脏受酒精/油腻刺激的敏感酶）今年都随减重明显回落，说明肝脏卸下了一部分油脂包袱。但空腹血糖（隔夜基础血糖）却从 2024 年 5.35 连续三年涨到 5.96，贴近 6.1 临界线；这说明虽然整体热量降了，但白天的精制碳水（白米白面、甜饮料）或长期睡不够 6.5 小时，让胰岛细胞始终处于偏高负荷。",
                "risk_if_ignored": "若放任空腹血糖继续每年爬升 0.2~0.3 mmol/L，1~3 年内很容易跨过 6.1 进入「空腹血糖受损（糖尿病前期）」，同时反过来拖慢脂肪肝的彻底消退。",
                "action_focus": "午餐/晚餐执行「先吃蔬菜与蛋白质，最后吃主食」，将一半白米饭换成杂粮或荞麦；把总睡眠稳定到 7 小时以上。",
            },
            {
                "priority": 2,
                "severity": "yellow",
                "title": "嘌呤代谢排泄轴：尿酸虽从红区回落，仍在 412 边缘游走",
                "linked_indicators": [
                    "嘌呤代谢产物｜血尿酸 412 μmol/L（正常参考：208—428）",
                ],
                "plain_why": "血尿酸（体内细胞代谢与食物嘌呤分解后的产物，主要靠肾脏排泄）2025 年曾冲高至 446 μmol/L 超标，2026 年戒夜宵并减少海鲜浓汤后回落到 412 μmol/L。虽然化验单上已经摘掉了红箭头，但它依然处在新上限 428 的 93% 高位区（临床上通常建议控制在 380 以下更稳妥），一次聚餐饮酒或熬夜就可能重新反弹。",
                "risk_if_ignored": "长期在 400~430 边缘震荡，尿酸盐微结晶容易在肾小管或足部小关节悄悄沉积，埋下痛风发作或肾结石隐患。",
                "action_focus": "继续严防老火海鲜汤、动物内脏、啤酒及含果葡糖浆饮料，保证每天饮白开水/淡茶 2000 ml 以上促进排酸。",
            },
            {
                "priority": 3,
                "severity": "red",
                "title": "甲状腺良性小结节定期随访：3.2mm 一年零变化，重在情绪与作息稳态",
                "linked_indicators": [
                    "超声提示｜甲状腺超声：甲状腺右叶小结节（TI-RADS 3类，约3.2mm，较前无明显变化）",
                ],
                "plain_why": "TI-RADS 3 类结节（超声科对甲状腺结节的良恶性分级体系，3 类代表绝大多数为良性，恶性风险低于 2%）且体积仅 3.2 毫米、连续两年大小稳定，属于临床最不需要过度焦虑的类型。常见诱因包括长期精神紧绷、熬夜缺觉与气机郁结。",
                "risk_if_ignored": "通常变化极慢，但长期熬夜与高频情绪内耗可能影响内分泌稳态，导致结节体积缓慢增大。",
                "action_focus": "无需吃药或急于穿刺，保持每年 1 次同院区同设备超声对比复查即可；避免长期焦虑熬夜。",
            },
        ],
        "system_analyses": [
            {
                "system_name": "糖代谢与胰岛负荷",
                "status": "yellow",
                "headline": "空腹血糖 3 年连涨至 5.96 mmol/L 逼近 6.1 上限，建议补查糖化血红蛋白。",
            },
            {
                "system_name": "血脂代谢全套",
                "status": "red",
                "headline": "甘油三酯 1.88 较去年大幅好转但仍微超 1.7，好胆固醇 HDL-C 1.38 表现稳健。",
            },
            {
                "system_name": "肾功能与泌尿系统",
                "status": "yellow",
                "headline": "血尿酸由 446 降至 412 μmol/L，摘掉红箭头但仍处 93% 临界高位需守住饮水。",
            },
            {
                "system_name": "肝胆功能与蛋白代谢",
                "status": "green",
                "headline": "ALT 34、GGT 46 均稳步回落至安全中段，轻度脂肪肝较前减轻。",
            },
            {
                "system_name": "心血管与心电图",
                "status": "green",
                "headline": "心电图正常窦性心律，穿戴静息心率一年内下降 6 bpm，心肺弹性向好。",
            },
            {
                "system_name": "血常规与炎症免疫",
                "status": "green",
                "headline": "超敏C反应蛋白 0.45 mg/L 处于极低水平，体内无明显慢性炎症信号。",
            },
        ],
        "food_therapy_plan": [
            {
                "category_name": "1. 燕窝与滋阴类",
                "badge_type": "yellow",
                "status_label": "可清炖可用 · 严禁冰糖",
                "red_light_avoid": "绝对避开市售即食冰糖燕窝、红枣桂圆高糖炖品与浓缩花胶糖水。当前空腹血糖已至 5.96 mmol/L 临界高位，添加糖会直接推高餐后血糖与甘油三酯合成。",
                "green_light_recommend": "若偏好滋阴润燥，可选用无糖纯燕窝（每周 2 次、每次干燕盏约 3g），仅以纯净水或少量铁皮石斛水隔水慢炖，不加任何糖浆与蜜饯。",
            },
            {
                "category_name": "2. 参类与虫草补气类",
                "badge_type": "yellow",
                "status_label": "清补可用 · 避开温燥红参",
                "red_light_avoid": "结合您自述的「口苦易上火」体感与轻度脂肪肝现状，暂不建议服用高丽参、红参片、鹿茸等大温大补之品，以免助生内热、加重口苦与睡眠浅。",
                "green_light_recommend": "日常提神解乏可用「西洋参 3g + 麦冬 5g」泡水代茶，性偏凉润，既缓解餐后困倦又兼顾生津稳糖。",
            },
            {
                "category_name": "3. 阿胶与膏滋厚味类",
                "badge_type": "red",
                "status_label": "阶段性慎用 · 先减脂再考虑",
                "red_light_avoid": "甘油三酯 1.88 仍微偏高且伴轻度脂肪肝与「餐后易困」痰湿偏重表现，阶段性避开阿胶糕（含大量黑芝麻、核桃、黄酒、冰糖）及浓缩厚腻膏方，以免脾胃运化不及导致血脂与体重反弹。",
                "green_light_recommend": "先用轻清利湿、消食化浊的食材把肝脏与血脂负担进一步卸下，待甘油三酯稳稳降回 1.5 以下且脂肪肝逆转后，再评估是否需要温和清补。",
            },
            {
                "category_name": "4. 药食同源日常茶饮",
                "badge_type": "green",
                "status_label": "重点推荐 · 疏通化浊稳糖",
                "red_light_avoid": "避开各类奶茶、果汁及配料表前三位含「果葡糖浆、白砂糖」的功能草本饮料；忌临睡前喝浓茶以免影响本就偏短的睡眠时长。",
                "green_light_recommend": "继续并在午后巩固饮用「葛根 6g + 新会陈皮 3g + 炒山楂 5g + 菊苣 6g」温水代茶（均属国家卫健委药食同源目录，兼顾化浊降脂、助排尿酸与护肝解腻）；下午 4 点后改喝白开水，保护夜间睡眠。",
            },
        ],
        "doctor_questions": [
            {
                "department": "内分泌科 / 全科健康管理",
                "question": "医生您好，我空腹血糖近三年从 5.35 慢慢涨到今年的 5.96 mmol/L（参考 3.9–6.1），虽然还没标红，我需要加测一次糖化血红蛋白（HbA1c）和餐后 2 小时血糖排查早期胰岛素抵抗吗？",
                "why_ask": "空腹血糖正常不代表餐后血糖正常，糖化血红蛋白能看清过去 3 个月的真实平均血糖，早筛成本极低且能抓住可逆窗口期。",
            },
            {
                "department": "消化内科 / 脂肪肝专病",
                "question": "我通过减重 3 kg，甘油三酯从去年 2.38 降到今年 1.88（参考 0.4–1.7），轻度脂肪肝也减轻了。目前不需要吃降脂药的话，再坚持 3 个月生活方式控制可以吗？",
                "why_ask": "确认您目前的改善节奏是否安全有效，避免无谓担忧吃药或遗漏复查时机。",
            },
            {
                "department": "甲状腺外科 / 普通外科",
                "question": "我甲状腺右叶 TI-RADS 3 类小结节（约 3.2 mm）连续两年大小和分类都没有变化，接下来还是保持一年一次常规超声随访就行吗？",
                "why_ask": "明确 3 类微小结节只需低频定期复查，卸下心理负担。",
            },
        ],
        "recheck_timeline": [
            {
                "timeframe": "1–2 周内（补齐盲区）",
                "items": "糖化血红蛋白（HbA1c）+ 餐后 2 小时血糖单项（社区或三甲门诊均可，费用约 40–60 元）",
                "goal": "看清 5.96 空腹血糖背后，餐后峰值和 3 个月平均糖代谢是否已进入糖耐量受损边缘。",
            },
            {
                "timeframe": "90 天后（效果闭环验证）",
                "items": "空腹血脂四项（重点盯甘油三酯与 LDL-C）、血尿酸、空腹血糖 + 肝功（ALT/GGT）",
                "goal": "验证睡眠拉回 7 小时 + 主食顺序调整 + 日常茶饮后，甘油三酯能否降回 1.7 以下、空腹血糖能否回落至 5.5 左右。",
            },
            {
                "timeframe": "12 个月后（年度常规对比）",
                "items": "腹部超声（复查脂肪肝消退情况）+ 甲状腺彩超（对比 3.2 mm 结节稳定性）",
                "goal": "完成全年度代谢与影像双线闭环。",
            },
        ],
        "disclaimer": "本报告为「Mirobody-Health」开源项目基于虚拟演示样本（林先生）生成的示例输出，仅作技术效果展示、健康风险科普与复查沟通参考，不构成任何医疗诊断、处方或用药依据；实际健康问题请及时前往正规医疗机构遵医嘱诊治。",
    }
