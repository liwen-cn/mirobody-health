import os
import json
import re
from src.api_client import call_deepseek_vision

EXTRACTION_PROMPT = """
你是一位顶尖的医学检验报告数据抽取专家。
请仔细查看这张医院检验报告单图片，将其中的所有化验指标准确提取并输出为严格的 JSON 格式。

要求：
1. 抹除并严禁包含任何个人隐私信息（不要包含姓名、病历号、床号、身份证等）。
2. 只提取医学检验指标，格式为 JSON 字典，必须包含：
   - "report_date": 报告日期（格式形如 "YYYY-MM-DD"，如从图片中看不出则填写大概日期如 "2026-10-23"）
   - "hospital": 医院名称（脱敏，可写 "三甲医院" 或留空）
   - "items": 数组，每个元素包含：
       - "name": 指标中文标准名（如 "甘油三酯"、"低密度脂蛋白胆固醇"、"总胆固醇"、"空腹血糖"、"尿酸"、"谷丙转氨酶" 等，去掉前面的星号*）
       - "abbr": 英文简称（如 "TG"、"LDL-C"、"TC"、"GLU"、"UA"、"ALT"）
       - "value": 检验数值（数字 float 或字符串）
       - "unit": 计量单位（如 "mmol/L"、"umol/L"、"U/L"）
       - "ref_range": 参考区间字符串（如 "0.45--1.70"、"<= 3.4"）
       - "status": 状态（"normal"、"high" 或 "low"）

只输出标准的 JSON 代码块，用 ```json 和 ``` 包裹，不要有多余说明。
"""

def extract_indicators_from_image(image_path, api_key):
    print(f"[*] 正在调用 DeepSeek Vision 识别: {image_path}...")
    content = call_deepseek_vision(image_path, EXTRACTION_PROMPT, api_key)
    
    # Extract json block
    m = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if m:
        json_str = m.group(1)
    else:
        json_str = content.strip()
    
    try:
        data = json.loads(json_str)
        return data
    except Exception as e:
        print(f"[!] JSON 解析失败: {e}\n原文内容:\n{content}")
        return None
