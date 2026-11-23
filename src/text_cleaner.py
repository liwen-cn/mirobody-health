import re

ABNORMAL_EXPLANATIONS = {
    "甘油三酯": {
        "condition": lambda val: val is not None and float(str(val).replace("*", "")) > 1.70,
        "indicator_meaning": "血液中脂肪含量的重要标志，主要来自食物摄入与肝脏合成。",
        "possible_consequences": "持续偏高会导致血液黏稠度增加、血流减缓，长期易加速动脉粥样硬化并诱发脂肪肝；若显著过高（>5.6 mmol/L）还会大幅增加诱发急性胰腺炎的风险。"
    },
    "总胆固醇": {
        "condition": lambda val: val is not None and float(str(val).replace("*", "")) > 5.20,
        "indicator_meaning": "血液中所有脂蛋白所含胆固醇的总和。",
        "possible_consequences": "过高易导致脂质在血管内皮沉积形成粥样硬化斑块，增加冠心病与脑卒中风险。"
    },
    "低密度脂蛋白胆固醇": {
        "condition": lambda val: val is not None and float(str(val).replace("*", "")) > 3.40,
        "indicator_meaning": "俗称“坏胆固醇”，负责将胆固醇运送到全身动脉壁。",
        "possible_consequences": "最主要的致动脉粥样硬化危险因素，超标会显著增加血管狭窄与血栓形成风险。"
    },
    "尿酸": {
        "condition": lambda val: val is not None and float(str(val).replace("*", "")) > 420,
        "indicator_meaning": "体内嘌呤代谢的终末产物，主要经肾脏排出。",
        "possible_consequences": "超标易析出微小尿酸盐结晶沉积于关节和肾小管，可能诱发痛风性关节炎、痛风石及肾功能隐匿性损伤。"
    },
    "葡萄糖(空腹)": {
        "condition": lambda val: val is not None and float(str(val).replace("*", "")) > 6.10,
        "indicator_meaning": "空腹状态下的血糖水平，反映基础胰岛素分泌与糖代谢稳态。",
        "possible_consequences": "持续偏高提示糖耐量受损或糖尿病风险，长期累积会损伤全身微血管与大血管（包括视网膜、肾脏及外周神经）。"
    },
    "丙氨酸氨基转移酶": {
        "condition": lambda val: val is not None and float(str(val).replace("*", "")) > 50,
        "indicator_meaning": "主要存在于肝细胞内，是肝实质细胞损伤最敏感的指标之一。",
        "possible_consequences": "升高提示肝细胞通透性增加或受损（如熬夜、脂肪肝、酒精或药物刺激），若持续不降易进展为肝脏慢性炎症。"
    }
}

def replace_abbreviations(text):
    """Thoroughly replace medical abbreviations with Chinese terms, handling Chinese word boundaries."""
    if not text:
        return ""
    # Avoid duplicate terms like 甘油三酯（TG） -> 甘油三酯
    text = re.sub(r'甘油三酯\s*（?\s*TG\s*）?', '甘油三酯', text, flags=re.IGNORECASE)
    text = re.sub(r'低密度脂蛋白胆固醇\s*（?\s*LDL-C\s*）?', '低密度脂蛋白胆固醇', text, flags=re.IGNORECASE)
    text = re.sub(r'高密度脂蛋白胆固醇\s*（?\s*HDL-C\s*）?', '高密度脂蛋白胆固醇', text, flags=re.IGNORECASE)
    text = re.sub(r'高密度脂蛋白\s*（?\s*HDL-C\s*）?', '高密度脂蛋白胆固醇', text, flags=re.IGNORECASE)
    text = re.sub(r'总胆固醇\s*（?\s*TC\s*）?', '总胆固醇', text, flags=re.IGNORECASE)
    text = re.sub(r'糖化血红蛋白\s*（?\s*HbA1c\s*）?', '糖化血红蛋白', text, flags=re.IGNORECASE)

    # Standalone acronyms
    text = re.sub(r'TG(?![a-zA-Z])', '甘油三酯', text)
    text = re.sub(r'LDL-C(?![a-zA-Z])', '低密度脂蛋白胆固醇', text, flags=re.IGNORECASE)
    text = re.sub(r'HDL-C(?![a-zA-Z])', '高密度脂蛋白胆固醇', text, flags=re.IGNORECASE)
    text = re.sub(r'TC(?![a-zA-Z])', '总胆固醇', text)
    text = re.sub(r'HbA1c(?![a-zA-Z])', '糖化血红蛋白', text, flags=re.IGNORECASE)
    text = re.sub(r'UA(?![a-zA-Z])', '尿酸', text)
    text = re.sub(r'ALT(?![a-zA-Z])', '谷丙转氨酶', text)
    text = re.sub(r'AST(?![a-zA-Z])', '谷草转氨酶', text)
    text = re.sub(r'GGT(?![a-zA-Z])', 'γ-谷氨酰转肽酶', text)
    text = re.sub(r'eGFR(?![a-zA-Z])', '肾小球滤过率', text)
    return text

def clean_forbidden_and_recommended(text):
    """
    Remove leading prefixes like 【提示不要用的】：, replace all abbreviations,
    and split numbered points into ordered list items.
    """
    if not text:
        return ""

    text = replace_abbreviations(text)

    # Remove headers
    text = re.sub(r'^【提示不要用的】[：:]\s*', '', text)
    text = re.sub(r'^【可以用的与推荐吃法】[：:]\s*', '', text)

    # Split by circled numbers ① ② ③ or 1. 2. 3.
    items = re.split(r'[①②③④⑤⑥⑦⑧⑨⑩]', text)
    items = [it.strip().rstrip('；;。') for it in items if it.strip()]

    # If no circled numbers found, try normal digits like 1. 2. 3.
    if len(items) <= 1:
        items = re.split(r'(?:^|\s+)\d+[.、]\s*', text)
        items = [it.strip().rstrip('；;。') for it in items if it.strip()]

    # If still not found, split by semicolon or periods if there are sentences
    if len(items) <= 1:
        raw_parts = [p.strip().rstrip('；;。') for p in re.split(r'[；;]', text) if p.strip()]
        if len(raw_parts) > 1:
            items = raw_parts
        else:
            items = [text.strip()]

    # Format into ordered HTML list
    html_items = "".join([f"<li>{item}</li>" for item in items])
    return f"<ol class='point-list'>{html_items}</ol>"
