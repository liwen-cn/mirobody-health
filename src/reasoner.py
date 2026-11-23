import json
import re
from src.api_client import call_deepseek_reasoner

PROJECT_TONIC_PROMPT = """
你是一位兼具现代临床代谢病学与高端滋补养生（燕窝、冬虫夏草、西洋参、石斛、药食同源茶饮）的权威健康管理专家。
以下是用户的全面历年健康数据跨期对比结果：
{comparison_json}

请对这份体检报告进行深度分析，完全去掉任何虚构的干预事件，直接基于真实数据走势，输出一份结构化、权威且通俗的指导方案。

具体要求分为两大部分：
第一部分：全面健康数据分析总结
1. overall_summary: 150字左右的综合健康评估（指出心脑血管脂质大盘的显著改善亮点，以及当前唯一的突出短板——甘油三酯持续走高）。
2. category_analyses: 数组，分别对以下四大系统进行“人话”透彻解读：
   - "血脂代谢"：解读LDL-C、总胆固醇大幅优化，但TG单边上升反映出的生活/饮食痛点。
   - "糖代谢"：解读空腹血糖与胰岛负荷状态。
   - "肾功能与尿酸"：解读尿酸连续两年改善下降的良性态势。
   - "肝胆代谢"：解读转氨酶与蛋白合成的健康稳态。

第二部分：分品类滋补与食养建议（分项目明确给出：提示不要用的、可以用的）
必须覆盖以下常见滋补品类，逐一明确红灯（不要用）与绿灯（可以用/如何用）：
1. "燕窝类（滋阴润燥）"
2. "冬虫夏草与参类（补气固本）"
3. "阿胶与膏滋类（滋补厚味）"
4. "药食同源茶饮（日常疏通调理）"

每个品类必须包含：
- "category_name": 品类名称
- "status": "谨慎使用/阶段性禁用" 或 "推荐可用/适度温补" 或 "重点推荐/日常疏通"
- "badge_type": "red" (禁用/谨慎) 或 "green" (可用)
- "forbidden_guidance": 【提示不要用的】：明确指出该品类中哪些具体吃法、人群阶段或配料属于禁忌，并讲清为什么（如高糖冰糖燕窝加重TG、阿胶滋腻碍胃阻滞气机、大热红参容易助热等）。
- "recommended_guidance": 【可以用的与推荐吃法】：如果能吃，具体推荐什么食材、吃法与用量（如纯燕窝无糖清炖、选用西洋参/铁皮石斛清补、山楂荷叶代茶饮消脂）。

第三部分：
- "next_review_plan": 建议复查的项目与周期（如 60~90 天复查血脂）。
- "disclaimer": 合规免责声明。

请严格返回符合上述结构的 JSON 对象，用 ```json 和 ``` 包裹。
"""

def generate_project_tonic_report(comparison_data, api_key):
    print("[*] 正在调用 DeepSeek 进行全面健康对比与分项滋补建议生成...")
    prompt = PROJECT_TONIC_PROMPT.format(comparison_json=json.dumps(comparison_data, ensure_ascii=False, indent=2))
    content = call_deepseek_reasoner(prompt, api_key)
    
    m = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if m:
        json_str = m.group(1)
    else:
        json_str = content.strip()
    
    try:
        return json.loads(json_str)
    except Exception as e:
        print(f"[!] JSON 解析失败: {e}\n{content}")
        return None
