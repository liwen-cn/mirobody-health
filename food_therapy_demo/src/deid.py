"""本地隐私脱敏网关：在数据发往云端 API 前抹除个人身份敏感信息。"""

import copy
import re
from typing import Any, Dict, List, Optional


ID_CARD_PATTERN = re.compile(r"\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b")
PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
LABELED_NAME_PATTERN = re.compile(r"(姓\s*名\s*[:：]\s*)([^\s,，;；|/\n]{2,6})")
LABELED_ID_PATTERN = re.compile(r"((?:体检号|住院号|门诊号|病历号|登记号|卡号|证件号|身份证号)\s*[:：]\s*)([A-Za-z0-9\-]{4,32})")
ADDRESS_PATTERN = re.compile(r"((?:住址|地址|联系地址|单位|工作单位)\s*[:：]\s*)([^\n]{4,60})")


def deidentify_text(text: str, extra_names: Optional[List[str]] = None) -> str:
    """对原始体检文本进行本地脱敏，抹除姓名、身份证号、手机号、住院/体检号等。"""
    if not text:
        return text

    masked = ID_CARD_PATTERN.sub("[已脱敏身份证号]", text)
    masked = PHONE_PATTERN.sub("[已脱敏手机号]", masked)
    masked = LABELED_NAME_PATTERN.sub(r"\1[已脱敏姓名]", masked)
    masked = LABELED_ID_PATTERN.sub(r"\1[已脱敏编号]", masked)
    masked = ADDRESS_PATTERN.sub(r"\1[已脱敏地址]", masked)

    if extra_names:
        for name in extra_names:
            name = name.strip()
            if len(name) >= 2:
                masked = masked.replace(name, "[已脱敏姓名]")

    return masked


def deidentify_payload(payload: Dict[str, Any], alias: str = "受检者A") -> Dict[str, Any]:
    """脱敏结构化体检数据包，仅保留代号、性别、年龄、脱敏指标与结论。"""
    cleaned = copy.deepcopy(payload)
    profile = cleaned.get("profile", {})
    raw_name = profile.get("name") or profile.get("real_name")
    extra_names = [raw_name] if isinstance(raw_name, str) and raw_name.strip() else []

    cleaned["profile"] = {
        "alias": profile.get("alias") or alias,
        "gender": profile.get("gender", "未知"),
        "age": profile.get("age", "未知"),
    }

    for report in cleaned.get("reports", []):
        if "hospital" in report and report["hospital"]:
            report["hospital"] = "体检机构"
        for finding in report.get("findings", []):
            if "summary" in finding and isinstance(finding["summary"], str):
                finding["summary"] = deidentify_text(finding["summary"], extra_names=extra_names)

    return cleaned
