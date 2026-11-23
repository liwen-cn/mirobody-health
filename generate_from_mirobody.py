#!/usr/bin/env python3
"""End-to-end CLI: Mirobody PostgreSQL -> Three-Layer Risk Miner -> DeepSeek-Flash -> HTML Report.

Usage:
    python3 generate_from_mirobody.py --demo --open
    python3 generate_from_mirobody.py --user-id 1 --label "家庭主档案"
"""

import argparse
import json
import os
import webbrowser
from datetime import datetime

from src.api_client import load_env
from src.demo_data import (
    get_offline_demo_report_json,
    load_demo_observations,
    load_demo_profile,
    load_demo_wearable_summary,
)
from src.mirobody_reader import fetch_user_medications, fetch_user_observations, fetch_wearable_summary
from src.proactive_reasoner import generate_proactive_report_json
from src.proactive_renderer import render_proactive_html
from src.risk_miner import mine_three_layer_risks


def run_pipeline(
    user_id="1",
    label="家庭健康档案",
    constitution_tags=None,
    gender="",
    age=None,
    recent_note="",
    include_demo=False,
    output_dir="output",
):
    env = load_env()
    api_key = os.environ.get("DEEPSEEK_API_KEY") or env.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 DEEPSEEK_API_KEY，请检查根目录 .env 文件。")

    print(f"[1/4] 正在从 Mirobody 数据库拉取 user_id={user_id} 的标准化体检数据...")
    observations = fetch_user_observations(user_id=user_id, include_demo=include_demo)
    if not observations:
        raise RuntimeError(f"user_id={user_id} 暂无真实上传的体检指标（请先在 Mirobody Web 上传报告）。")
    medications = fetch_user_medications(user_id=user_id)
    wearable_summary = fetch_wearable_summary(user_id=user_id)
    wearable_msg = (
        f"，Apple Watch 穿戴汇总 {wearable_summary['date_span']['total_days']} 天"
        f"（{wearable_summary['date_span']['first_day']} ~ {wearable_summary['date_span']['last_day']}）"
        if wearable_summary.get("has_data")
        else ""
    )
    print(f"      已拉取 {len(observations)} 条标准化体检记录，{len(medications)} 条用药记录{wearable_msg}。")

    user_profile = {
        "code_name": label,
        "gender": (gender or "").strip(),
        "age": age,
        "constitution_tags": constitution_tags or [],
        "recent_note": (recent_note or "").strip(),
    }

    print("[2/4] 正在运行「三层主动风险挖掘引擎」（显性红牌 / 隐性临界黄牌 / 跨系统分组）...")
    mined = mine_three_layer_risks(observations, medications=medications, user_profile=user_profile)
    stats = mined["summary_stats"]
    print(
        f"      预筛完成：共 {stats['total_observations']} 项 | "
        f"🔴 显性异常 {stats['red_count']} 项 | "
        f"🟡 隐性临界 {stats['yellow_count']} 项 | "
        f"🟢 保护亮点 {len(mined['protective_highlights'])} 项"
    )

    print("[3/4] 正在调用 DeepSeek-Flash 进行跨系统联动痛点归因与红绿灯食养方案推理...")
    report_json = generate_proactive_report_json(
        mined,
        api_key,
        user_profile=user_profile,
        wearable_summary=wearable_summary,
    )

    print("[4/4] 正在渲染高颜值手机/打印自适应 HTML 报告...")
    html_content = render_proactive_html(
        mined,
        report_json,
        user_label=label,
        user_profile=user_profile,
        wearable_summary=wearable_summary,
    )

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"mirobody_proactive_report_u{user_id}_{ts}"
    html_path = os.path.join(output_dir, f"{base_name}.html")
    json_path = os.path.join(output_dir, f"{base_name}.json")
    latest_path = os.path.join(output_dir, "latest_mirobody_report.html")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "user_profile": user_profile,
                "mined_summary": stats,
                "wearable_summary": wearable_summary,
                "report": report_json,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"[✓] 报告生成成功！")
    print(f"    HTML 报告：{os.path.abspath(html_path)}")
    print(f"    最新快捷链接：{os.path.abspath(latest_path)}")
    return html_path, json_path, report_json, mined


def run_demo_pipeline(use_live_llm=False, output_dir="output", open_browser=False):
    """Run the full risk-mining + rendering pipeline on a built-in synthetic demo profile."""
    user_profile = load_demo_profile()
    label = user_profile["code_name"]

    print(f"[1/4] 正在加载内置脱敏演示样本（{label}，2024~2026 体检指标 + 模拟穿戴趋势）...")
    observations = load_demo_observations()
    wearable_summary = load_demo_wearable_summary()
    print(
        f"      已加载 {len(observations)} 条脱敏体检记录，"
        f"Apple Watch 模拟汇总 {wearable_summary['date_span']['total_days']} 天。"
    )

    print("[2/4] 正在运行「三层主动风险挖掘引擎」（显性红牌 / 隐性临界黄牌 / 跨系统分组）...")
    mined = mine_three_layer_risks(observations, medications=[], user_profile=user_profile)
    stats = mined["summary_stats"]
    print(
        f"      预筛完成：共 {stats['total_observations']} 项 | "
        f"🔴 显性异常 {stats['red_count']} 项 | "
        f"🟡 隐性临界 {stats['yellow_count']} 项 | "
        f"🟢 保护亮点 {len(mined['protective_highlights'])} 项"
    )

    if use_live_llm:
        env = load_env()
        api_key = os.environ.get("DEEPSEEK_API_KEY") or env.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("使用 --demo-live 需要配置 DEEPSEEK_API_KEY（请复制 .env.example 为 .env 并填入 Key）。")
        print("[3/4] 正在实时调用 DeepSeek-Flash 对演示样本进行跨系统推理...")
        report_json = generate_proactive_report_json(
            mined,
            api_key,
            user_profile=user_profile,
            wearable_summary=wearable_summary,
        )
    else:
        print("[3/4] 正在加载离线预合成推理结果（无需 API Key；如需实时推理请加 --demo-live）...")
        report_json = get_offline_demo_report_json()

    print("[4/4] 正在渲染高颜值手机/打印自适应 HTML 报告...")
    html_content = render_proactive_html(
        mined,
        report_json,
        user_label=label,
        user_profile=user_profile,
        wearable_summary=wearable_summary,
    )

    os.makedirs(output_dir, exist_ok=True)
    html_path = os.path.join(output_dir, "demo_mirobody_report.html")
    json_path = os.path.join(output_dir, "demo_mirobody_report.json")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "user_profile": user_profile,
                "mined_summary": stats,
                "wearable_summary": wearable_summary,
                "report": report_json,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    abs_html = os.path.abspath(html_path)
    print("[✓] 演示报告生成成功！")
    print(f"    HTML 报告：{abs_html}")
    if open_browser:
        webbrowser.open("file://" + abs_html)
    return html_path, json_path, report_json, mined


def main():
    parser = argparse.ArgumentParser(description="Mirobody 主动健康风险挖掘与食养报告生成器")
    parser.add_argument("--demo", action="store_true", help="使用内置脱敏演示样本运行极速体验（无需 Docker / API Key）")
    parser.add_argument("--demo-live", action="store_true", help="配合 --demo 使用，实时调用 DeepSeek-Flash API 推理")
    parser.add_argument("--output-dir", default="output", help="输出目录（默认 output）")
    parser.add_argument("--open", action="store_true", help="生成完成后在默认浏览器中自动打开报告")
    parser.add_argument("--user-id", default="1", help="Mirobody 用户 ID（默认 1）")
    parser.add_argument("--label", default="家庭主档案", help="脱敏显示代号")
    parser.add_argument("--gender", default="", choices=["", "男", "女"], help="性别（男/女，选填）")
    parser.add_argument("--age", type=int, default=None, help="年龄（周岁，选填）")
    parser.add_argument("--note", default="", help="近期用药或调理一句话备注（选填）")
    parser.add_argument("--tags", nargs="*", default=[], help="可选体质/体感标签（如 餐后易困 熬夜）")
    parser.add_argument("--include-demo", action="store_true", help="是否包含 Mirobody 自带演示数据")
    args = parser.parse_args()

    if args.demo or args.demo_live:
        run_demo_pipeline(
            use_live_llm=args.demo_live,
            output_dir=args.output_dir,
            open_browser=args.open,
        )
        return

    html_path, _, _, _ = run_pipeline(
        user_id=args.user_id,
        label=args.label,
        constitution_tags=args.tags,
        gender=args.gender,
        age=args.age,
        recent_note=args.note,
        include_demo=args.include_demo,
        output_dir=args.output_dir,
    )
    if args.open:
        webbrowser.open("file://" + os.path.abspath(html_path))


if __name__ == "__main__":
    main()
