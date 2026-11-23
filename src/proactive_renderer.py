"""Render the Proactive Three-Layer Health Risk & Food-Therapy Report into a polished, mobile-friendly HTML document."""

import html
import re
from collections import defaultdict
from datetime import datetime

from src.risk_miner import parse_ref_range


def _esc(val):
    return html.escape(str(val or ""))


def _strip_ft_prefix(text):
    """Strip redundant leading '【先排雷...】' / '【可安心用...】' prefixes from food-therapy body text."""
    s = str(text or "").strip()
    s = re.sub(
        r"^(?:【(?:先排雷[^】]*|可安心用[^】]*)】|先排雷\s*[·・\-—]?\s*千万别乱吃|可安心用\s*[·・\-—]?\s*推荐搭配与吃法)\s*[:：]?\s*",
        "",
        s,
    )
    return s.strip()


def _grade_style(grade):
    g = str(grade or "")
    if "尽快" in g or "就医" in g:
        return ("#991b1b", "#fef2f2", "#fecaca")
    if "重点" in g:
        return ("#b45309", "#fffbeb", "#fde68a")
    if "轻度" in g:
        return ("#1d4ed8", "#eff6ff", "#bfdbfe")
    return ("#065f46", "#ecfdf5", "#a7f3d0")


def _render_sparkline_svg(years, pts, color, uid):
    """Render a crisp, zero-dependency inline SVG sparkline with value labels and year ticks.

    pts: list of tuples (year_str, value_or_None, days_int)
    """
    valid = [(i, p[1], p[2]) for i, p in enumerate(pts) if p[1] is not None]
    if not valid:
        return ""

    w, h = 220, 78
    pad_l, pad_r, pad_t, pad_b = 22, 22, 20, 18
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    n = len(years)

    vals = [v for _, v, _ in valid]
    vmin, vmax = min(vals), max(vals)
    span = vmax - vmin
    if span < 1e-6:
        span = max(abs(vmax) * 0.2, 1.0)
        vmin -= span * 0.5
        vmax += span * 0.5

    def _xy(idx, val):
        x = pad_l + (plot_w * idx / max(n - 1, 1))
        y = pad_t + plot_h * (1.0 - (val - vmin) / span)
        return round(x, 1), round(y, 1)

    coords = [(_xy(i, v), v, d, i) for i, v, d in valid]
    poly_pts = " ".join(f"{x},{y}" for (x, y), _, _, _ in coords)
    base_y = pad_t + plot_h
    area_pts = (
        f"{coords[0][0][0]},{base_y} "
        + poly_pts
        + f" {coords[-1][0][0]},{base_y}"
    )

    dots_and_labels = []
    for (x, y), val, days, _ in coords:
        is_small = days < 30
        fill = "#ffffff" if is_small else color
        val_str = f"{int(val)}" if isinstance(val, int) or float(val).is_integer() else f"{val}"
        dots_and_labels.append(
            f'<circle cx="{x}" cy="{y}" r="3.4" fill="{fill}" stroke="{color}" stroke-width="2" />'
        )
        dots_and_labels.append(
            f'<text x="{x}" y="{max(y - 7, 11)}" text-anchor="middle" font-size="10" '
            f'font-weight="700" fill="#1f2933">{_esc(val_str)}</text>'
        )

    x_ticks = []
    for i, yr in enumerate(years):
        tx = round(pad_l + (plot_w * i / max(n - 1, 1)), 1)
        x_ticks.append(
            f'<text x="{tx}" y="{h - 3}" text-anchor="middle" font-size="9.5" fill="#6b7280">{_esc(yr)}</text>'
        )

    grad_id = f"sg_{uid}"
    return (
        f'<svg class="w-svg" viewBox="0 0 {w} {h}" width="100%" height="{h}" xmlns="http://www.w3.org/2000/svg">'
        f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.22"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0.01"/>'
        f'</linearGradient></defs>'
        f'<line x1="{pad_l}" y1="{base_y}" x2="{w - pad_r}" y2="{base_y}" stroke="#e5e7eb" stroke-width="1"/>'
        f'<polygon points="{area_pts}" fill="url(#{grad_id})" />'
        f'<polyline fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" points="{poly_pts}" />'
        f'{"".join(dots_and_labels)}'
        f'{"".join(x_ticks)}'
        f'</svg>'
    )


def _render_lab_spark_svg(pts, color, uid, ref_line=None, ref_label=""):
    """Render an inline SVG trend chart for a multi-date lab indicator with an optional reference line.

    pts: list of (date_str, value_num) sorted ascending (capped to last 6 points for readability).
    """
    pts = pts[-6:]
    if len(pts) < 2:
        return ""

    w, h = 230, 82
    pad_l, pad_r, pad_t, pad_b = 22, 22, 20, 18
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    n = len(pts)

    vals = [v for _, v in pts]
    all_v = list(vals)
    if ref_line is not None:
        all_v.append(ref_line)
    vmin, vmax = min(all_v), max(all_v)
    span = vmax - vmin
    if span < 1e-6:
        span = max(abs(vmax) * 0.2, 1.0)
        vmin -= span * 0.5
        vmax += span * 0.5
    else:
        # Give slight headroom/footroom so labels and ref line don't collide
        vmin -= span * 0.12
        vmax += span * 0.12
        span = vmax - vmin

    def _xy(idx, val):
        x = pad_l + (plot_w * idx / max(n - 1, 1))
        y = pad_t + plot_h * (1.0 - (val - vmin) / span)
        return round(x, 1), round(y, 1)

    coords = [(_xy(i, v), d, v) for i, (d, v) in enumerate(pts)]
    poly_pts = " ".join(f"{x},{y}" for (x, y), _, _ in coords)
    base_y = pad_t + plot_h
    area_pts = f"{coords[0][0][0]},{base_y} {poly_pts} {coords[-1][0][0]},{base_y}"

    ref_svg = ""
    if ref_line is not None:
        _, ry = _xy(0, ref_line)
        ref_svg = (
            f'<line x1="{pad_l}" y1="{ry}" x2="{w - pad_r}" y2="{ry}" '
            f'stroke="#dc2626" stroke-width="1" stroke-dasharray="3,3" opacity="0.65" />'
            f'<text x="{w - pad_r}" y="{max(ry - 3, 10)}" text-anchor="end" font-size="8.5" '
            f'font-weight="600" fill="#dc2626" opacity="0.85">{_esc(ref_label)}</text>'
        )

    dots_and_labels = []
    x_ticks = []
    for i, ((x, y), dstr, val) in enumerate(coords):
        val_str = f"{int(val)}" if float(val).is_integer() else f"{round(val, 2)}"
        dots_and_labels.append(
            f'<circle cx="{x}" cy="{y}" r="3.3" fill="{color}" stroke="#ffffff" stroke-width="1.4" />'
        )
        dots_and_labels.append(
            f'<text x="{x}" y="{max(y - 6, 11)}" text-anchor="middle" font-size="9.5" '
            f'font-weight="700" fill="#1f2933">{_esc(val_str)}</text>'
        )
        # Format YYYY-MM-DD -> YY.MM
        short_d = dstr[2:7].replace("-", ".") if len(dstr) >= 7 else dstr
        if n <= 4 or i in (0, n - 1) or i % 2 == 0:
            x_ticks.append(
                f'<text x="{x}" y="{h - 3}" text-anchor="middle" font-size="9" fill="#6b7280">{_esc(short_d)}</text>'
            )

    grad_id = f"lg_{uid}"
    return (
        f'<svg class="w-svg" viewBox="0 0 {w} {h}" width="100%" height="{h}" xmlns="http://www.w3.org/2000/svg">'
        f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.18"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0.01"/>'
        f'</linearGradient></defs>'
        f'<line x1="{pad_l}" y1="{base_y}" x2="{w - pad_r}" y2="{base_y}" stroke="#e5e7eb" stroke-width="1"/>'
        f'{ref_svg}'
        f'<polygon points="{area_pts}" fill="url(#{grad_id})" />'
        f'<polyline fill="none" stroke="{color}" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" points="{poly_pts}" />'
        f'{"".join(dots_and_labels)}'
        f'{"".join(x_ticks)}'
        f'</svg>'
    )


def render_proactive_html(mined_data, report_json, user_label="家庭健康档案", user_profile=None, wearable_summary=None):
    stats = mined_data["summary_stats"]
    dates = stats.get("report_dates", [])
    date_span = f"{dates[0]} ～ {dates[-1]}" if len(dates) >= 2 else (dates[0] if dates else "未知日期")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    profile = user_profile or {}
    profile_parts = []
    if profile.get("gender"):
        profile_parts.append(str(profile["gender"]))
    if profile.get("age"):
        profile_parts.append(f"{profile['age']}岁")
    profile_badge_html = (
        f"<span>基础画像：{_esc(' · '.join(profile_parts))}</span>"
        if profile_parts
        else ""
    )
    recent_note = str(profile.get("recent_note") or "").strip()
    recent_note_html = (
        f'<div class="hero-note">近期用药/调理备注：{_esc(recent_note)}</div>'
        if recent_note
        else ""
    )

    title = report_json.get("report_title", "AI 主动健康风险洞察与四季食养报告")
    grade = report_json.get("overall_grade", "重点干预")
    grade_fg, grade_bg, grade_bd = _grade_style(grade)
    exec_summary = report_json.get("executive_summary", "")

    def _render_metric_chips(metrics, variant):
        if not metrics or not isinstance(metrics, list):
            return ""
        cls_variant = "em-good" if variant == "good" else ("em-red" if variant == "red" else "em-yellow")
        chips = []
        for m in metrics:
            if not isinstance(m, dict):
                continue
            plain_raw = str(m.get("plain_name") or m.get("term") or "").strip()
            term_raw = str(m.get("term") or "").strip()
            term_html = (
                f'<span class="em-term">（{_esc(term_raw)}）</span>'
                if term_raw and term_raw != plain_raw
                else ""
            )
            status_raw = str(m.get("status") or "").strip()
            status_html = f'<span class="em-status">{_esc(status_raw)}</span>' if status_raw else ""
            val_raw = str(m.get("value") or "").strip()
            ref_raw = str(m.get("ref") or "").strip()
            val_html = f'<span>你的结果：<strong>{_esc(val_raw)}</strong></span>' if val_raw else ""
            ref_html = f'<span class="em-ref">参考：{_esc(ref_raw)}</span>' if ref_raw else ""
            chips.append(
                f'<div class="em-chip {cls_variant}">'
                f'<div class="em-top"><span class="em-name"><strong>{_esc(plain_raw)}</strong>{term_html}</span>{status_html}</div>'
                f'<div class="em-vals">{val_html}{ref_html}</div>'
                f'</div>'
            )
        return f'<div class="exec-metrics">{"".join(chips)}</div>' if chips else ""

    if isinstance(exec_summary, dict) and any(
        k in exec_summary for k in ("one_line_verdict", "good_news", "watch_items", "first_step")
    ):
        sections = []
        verdict = str(exec_summary.get("one_line_verdict") or "").strip()
        if verdict:
            sections.append(f'<div class="exec-verdict">{_esc(verdict)}</div>')

        good_news = exec_summary.get("good_news") if isinstance(exec_summary.get("good_news"), dict) else {}
        gn_summary = str(good_news.get("summary") or "").strip()
        gn_chips = _render_metric_chips(good_news.get("metrics"), "good")
        if gn_summary or gn_chips:
            gn_p = f'<p class="exec-sec-p">{_esc(gn_summary)}</p>' if gn_summary else ""
            sections.append(
                f'<div class="exec-sec exec-good">'
                f'<div class="exec-sec-title">✅ 先吃颗定心丸（底子好的地方）</div>'
                f'{gn_p}{gn_chips}'
                f'</div>'
            )

        watch_items = exec_summary.get("watch_items") if isinstance(exec_summary.get("watch_items"), list) else []
        w_items_html = []
        for idx, wi in enumerate(watch_items, 1):
            if not isinstance(wi, dict):
                continue
            sev = "red" if wi.get("severity") == "red" else "yellow"
            num_cls = "ew-num-red" if sev == "red" else "ew-num-yellow"
            wi_title = str(wi.get("title") or "").strip()
            wi_explain = str(wi.get("plain_explain") or "").strip()
            wi_explain_html = f'<p class="ew-explain">{_esc(wi_explain)}</p>' if wi_explain else ""
            wi_chips = _render_metric_chips(wi.get("metrics"), sev)
            w_items_html.append(
                f'<div class="exec-watch-item">'
                f'<div class="ew-head"><span class="ew-num {num_cls}">{idx}</span><span class="ew-title">{_esc(wi_title)}</span></div>'
                f'{wi_explain_html}{wi_chips}'
                f'</div>'
            )
        if w_items_html:
            sections.append(
                f'<div class="exec-sec exec-watch">'
                f'<div class="exec-sec-title">⚠️ 眼下最该盯紧的 {len(w_items_html)} 件事</div>'
                f'<div class="exec-watch-list">{"".join(w_items_html)}</div>'
                f'</div>'
            )

        first_step = str(exec_summary.get("first_step") or "").strip()
        if first_step:
            sections.append(
                f'<div class="exec-sec exec-step">'
                f'<div class="exec-sec-title">🎯 现在最省力的第一步</div>'
                f'<p class="exec-sec-p" style="margin-bottom:0;">{_esc(first_step)}</p>'
                f'</div>'
            )

        exec_body_html = "\n".join(sections)
    else:
        exec_body_html = f'<p style="margin:0; font-size:14.5px;">{_esc(exec_summary)}</p>'

    # 0.5 Silent Borderline Early-Warning Callout (indicators NOT flagged red on original report)
    yellow_by_name = {}
    for yf in mined_data.get("layer2_yellow_flags", []):
        yname = yf.get("name", "")
        if yname:
            prev = yellow_by_name.get(yname)
            if not prev or (yf.get("report_date", "") >= prev.get("report_date", "")):
                yellow_by_name[yname] = yf
    silent_callout_html = ""
    if yellow_by_name:
        priority_kw = ("糖化血红蛋白", "葡萄糖(空腹)", "空腹血糖", "甘油三酯", "尿酸", "估算肾小球滤过率", "肌酐", "尿素")
        ordered_y = sorted(
            yellow_by_name.values(),
            key=lambda x: (
                0 if any(k in x.get("name", "") for k in priority_kw) else 1,
                -(len(x.get("report_date", ""))),
            ),
        )
        examples = [
            (
                f"{it['name']} {it['value_text']}（参考 {it['ref_text']}）".strip()
                if it.get("ref_text")
                else f"{it['name']} {it['value_text']}".strip()
            )
            for it in ordered_y[:3]
        ]
        ex_txt = "、".join(examples)
        silent_callout_html = (
            f'<div class="silent-callout">'
            f'<strong>💡 隐性早筛提醒：</strong>原体检单未标异常的指标中，系统提前揪出 '
            f'<strong>{len(yellow_by_name)} 项</strong>已逼近警戒线的边缘信号'
            f'（如 {_esc(ex_txt)} 等）——此时靠作息与饮食微调代价最小，别等画上红箭头才干预。'
            f'</div>'
        )

    # 1. Protective Highlights
    prot_cards = []
    for p in report_json.get("protective_highlights", []):
        prot_cards.append(f"""
        <div class="prot-card">
          <div class="prot-top">
            <span class="prot-dot"></span>
            <span class="prot-title">{_esc(p.get("title"))}</span>
          </div>
          <div class="prot-val-row"><span class="prot-val">{_esc(p.get("evidence"))}</span></div>
          <div class="prot-meaning">{_esc(p.get("meaning"))}</div>
        </div>""")
    prot_html = "\n".join(prot_cards)

    # Build multi-date lab series lookup for inline trend charts inside Core Pain Points
    lab_series_map = {}
    _raw_lab_pts = defaultdict(list)
    for sb in mined_data.get("systems", []):
        for item in sb.get("items", []):
            if item.get("value_num") is not None and item.get("report_date") and item.get("name"):
                _raw_lab_pts[item["name"]].append(item)
    for lname, items in _raw_lab_pts.items():
        by_date = {}
        for it in sorted(items, key=lambda x: x["report_date"]):
            by_date[it["report_date"]] = it
        if len(by_date) >= 2:
            ordered = [by_date[d] for d in sorted(by_date.keys())]
            latest = ordered[-1]
            low, high, mode = parse_ref_range(latest.get("ref_text", ""))
            ref_line, ref_label = None, ""
            if mode in ("closed", "upper") and high is not None:
                ref_line, ref_label = high, f"上限 {high}"
            elif mode == "lower" and low is not None:
                ref_line, ref_label = low, f"下限 {low}"
            lab_series_map[lname] = {
                "name": lname,
                "unit": latest.get("unit", ""),
                "latest_val": latest.get("value_text", ""),
                "risk_level": latest.get("risk_level", "normal"),
                "direction": latest.get("direction", ""),
                "pts": [(it["report_date"], float(it["value_num"])) for it in ordered],
                "ref_line": ref_line,
                "ref_label": ref_label,
            }
    # Sort candidate names longest-first to avoid partial substring mismatches (e.g. 肌酐 vs 尿白蛋白/肌酐)
    _lab_names_sorted = sorted(lab_series_map.keys(), key=len, reverse=True)

    # 2. Core Pain Points (Layer 3)
    pain_cards = []
    for idx, pp in enumerate(report_json.get("core_pain_points", []), 1):
        sev = pp.get("severity", "yellow")
        sev_cls = "sev-red" if sev == "red" else "sev-yellow"
        sev_tag = "🔴 显性高优痛点" if sev == "red" else "🟡 隐性临界预警"

        matched_charts = []
        seen_lab_names = set()
        remaining_pills = []
        for ind in pp.get("linked_indicators", []):
            ind_str = str(ind or "")
            hit_name = None
            for cand in _lab_names_sorted:
                if cand in ind_str:
                    hit_name = cand
                    break
            if hit_name:
                if hit_name not in seen_lab_names:
                    seen_lab_names.add(hit_name)
                    matched_charts.append(lab_series_map[hit_name])
            else:
                remaining_pills.append(ind_str)

        charts_html = ""
        if matched_charts:
            c_items = []
            for c_idx, ch in enumerate(matched_charts):
                rlvl = ch["risk_level"]
                c_color = "#b91c1c" if rlvl == "red" else ("#b45309" if rlvl == "yellow" else "#134e4a")
                c_tag_cls = "wd-red" if rlvl == "red" else ("wd-warn" if rlvl == "yellow" else "wd-good")
                c_tag_txt = (
                    "原单未标红 · 边缘黄灯"
                    if rlvl == "yellow"
                    else (ch["direction"] or ("异常" if rlvl == "red" else "平稳"))
                )
                svg_c = _render_lab_spark_svg(
                    ch["pts"],
                    c_color,
                    f"p{idx}_{c_idx}",
                    ref_line=ch["ref_line"],
                    ref_label=ch["ref_label"],
                )
                c_items.append(f"""
                <div class="lab-spark-card">
                  <div class="w-spark-top">
                    <span class="w-spark-name">{_esc(ch["name"])}</span>
                    <span class="w-delta {c_tag_cls}">{_esc(c_tag_txt)}</span>
                  </div>
                  <div class="w-spark-val"><strong>{_esc(ch["latest_val"])}</strong> <span>{_esc(ch["unit"])}</span><em>最新</em></div>
                  {svg_c}
                </div>""")
            charts_html = f'<div class="lab-spark-grid">{"".join(c_items)}</div>'

        pills = "".join(f'<span class="ind-pill">{_esc(ind)}</span>' for ind in remaining_pills)
        pills_block = f'<div class="pain-pills">{pills}</div>' if pills else ""

        pain_cards.append(f"""
        <div class="pain-card {sev_cls}">
          <div class="pain-header">
            <span class="pain-badge">{sev_tag} · TOP {pp.get("priority", idx)}</span>
            <h3 class="pain-title">{_esc(pp.get("title"))}</h3>
          </div>
          {charts_html}
          {pills_block}
          <div class="pain-grid">
            <div class="pain-block">
              <div class="pain-label">医生没空细讲的大白话</div>
              <p>{_esc(pp.get("plain_why"))}</p>
            </div>
            <div class="pain-block pain-warn-box">
              <div class="pain-label">放任不管 1～3 年可能演变为</div>
              <p>{_esc(pp.get("risk_if_ignored"))}</p>
            </div>
          </div>
          <div class="pain-action">
            <strong>优先抓手：</strong>{_esc(pp.get("action_focus"))}
          </div>
        </div>""")
    pain_html = "\n".join(pain_cards)

    # 3. Full-System Traffic-Light One-Screen Overview (compact: name + badge + 1-line conclusion, no redundant long paragraphs)
    sys_cards = []
    for sa in report_json.get("system_analyses", []):
        st = sa.get("status", "green")
        sname = str(sa.get("system_name", ""))
        st_cls = "st-red" if st == "red" else ("st-yellow" if st == "yellow" else "st-green")
        st_txt = "需重点关注" if st == "red" else ("临界警戒" if st == "yellow" else "整体稳健")
        sys_cards.append(f"""
        <div class="sys-summary-card {st_cls}">
          <div class="sys-summary-head">
            <span class="sys-summary-name">{_esc(sname)}</span>
            <span class="sys-pill {st_cls}">{st_txt}</span>
          </div>
          <div class="sys-headline">{_esc(sa.get("headline"))}</div>
        </div>""")
    sys_summary_section_html = (
        f"""
  <h2 class="section-title">三、分系统红绿灯一屏总览</h2>
  <div class="section-sub">全系统状态速览（红黄牌深度拆解见第一部分，全部原始数值见文末底表）</div>
  <div class="sys-grid">{"".join(sys_cards)}</div>"""
        if sys_cards
        else ""
    )

    # 4. Food Therapy Red/Green Cards
    ft_cards = []
    for ft in report_json.get("food_therapy_plan", []):
        bt = ft.get("badge_type", "yellow")
        bt_cls = "ft-red" if bt == "red" else ("ft-green" if bt == "green" else "ft-yellow")
        ft_cards.append(f"""
        <div class="ft-card">
          <div class="ft-head">
            <h4>{_esc(ft.get("category_name"))}</h4>
            <span class="ft-badge {bt_cls}">{_esc(ft.get("status_label"))}</span>
          </div>
          <div class="ft-body">
            <div class="ft-avoid">
              <div class="ft-sub-title avoid-t">🔴 先排雷 · 千万别乱吃</div>
              <p>{_esc(_strip_ft_prefix(ft.get("red_light_avoid")))}</p>
            </div>
            <div class="ft-rec">
              <div class="ft-sub-title rec-t">🟢 可安心用 · 推荐搭配与吃法</div>
              <p>{_esc(_strip_ft_prefix(ft.get("green_light_recommend")))}</p>
            </div>
          </div>
        </div>""")
    ft_html = "\n".join(ft_cards)

    # 5. Doctor Questions
    doc_cards = []
    for idx, dq in enumerate(report_json.get("doctor_questions", []), 1):
        doc_cards.append(f"""
        <div class="doc-card">
          <div class="doc-top">
            <span class="doc-num">Q{idx}</span>
            <span class="doc-dept">{_esc(dq.get("department"))}</span>
          </div>
          <div class="doc-q">“{_esc(dq.get("question"))}”</div>
          <div class="doc-why">排查目的：{_esc(dq.get("why_ask"))}</div>
        </div>""")
    doc_html = "\n".join(doc_cards)

    # 6. Recheck Timeline
    recheck_rows = []
    for rc in report_json.get("recheck_timeline", []):
        recheck_rows.append(f"""
        <div class="rc-item">
          <div class="rc-time">{_esc(rc.get("timeframe"))}</div>
          <div class="rc-content">
            <div class="rc-items">{_esc(rc.get("items"))}</div>
            <div class="rc-goal">验证目标：{_esc(rc.get("goal"))}</div>
          </div>
        </div>""")
    recheck_html = "\n".join(recheck_rows)

    # 6.5 Apple Watch / Wearable Trend & Lab Cross-Check (only shown when wearable data exists)
    wearable_section_html = ""
    ws = wearable_summary if (wearable_summary and wearable_summary.get("has_data")) else None
    wi = report_json.get("wearable_insights") if isinstance(report_json.get("wearable_insights"), dict) else None
    if ws:
        span_txt = ""
        if ws.get("date_span"):
            ds = ws["date_span"]
            span_txt = f"Apple Watch 历史跨度：{ds.get('first_day', '')} ～ {ds.get('last_day', '')}（共 {ds.get('total_days', 0)} 天）"

        wi_headline = f'<div class="w-headline">{_esc(wi.get("headline"))}</div>' if (wi and wi.get("headline")) else ""

        cross_text = str((wi or {}).get("lab_cross_check") or "").strip()
        action_text = str((wi or {}).get("action_focus") or "").strip()
        # Backward-compat: extract "最省力的抓手：..." from lab_cross_check if action_focus not separate
        if not action_text and "抓手：" in cross_text:
            parts = cross_text.split("最省力的抓手：", 1)
            if len(parts) == 2:
                cross_text = parts[0].strip()
                action_text = parts[1].strip()
            else:
                parts2 = cross_text.split("抓手：", 1)
                if len(parts2) == 2:
                    cross_text = parts2[0].strip()
                    action_text = parts2[1].strip()

        wi_cross = f'<p class="w-cross">{_esc(cross_text)}</p>' if cross_text else ""
        wi_action = (
            f'<div class="w-action"><strong>🎯 最省力的生活抓手：</strong>{_esc(action_text)}</div>'
            if action_text
            else ""
        )

        pills_html = ""
        if wi:
            hi_list = wi.get("highlights") or []
            wa_list = wi.get("warnings") or []
            if hi_list or wa_list:
                hi_li = "".join(f"<li>{_esc(x)}</li>" for x in hi_list)
                wa_li = "".join(f"<li>{_esc(x)}</li>" for x in wa_list)
                hi_col = f'<div class="w-col w-col-green"><div class="w-col-t">✓ 正向行为证据</div><ul>{hi_li}</ul></div>' if hi_li else ""
                wa_col = f'<div class="w-col w-col-amber"><div class="w-col-t">⚠ 需关注的恢复短板</div><ul>{wa_li}</ul></div>' if wa_li else ""
                pills_html = f'<div class="w-cols">{hi_col}{wa_col}</div>'

        spark_grid_html = ""
        if ws and ws.get("yearly_trend"):
            yt = ws["yearly_trend"]
            years = sorted(yt.keys())
            # (label, unit, polarity: 'higher'|'lower'|'neutral')
            spark_specs = [
                ("日均步数", "步", "higher"),
                ("日均锻炼时长", "分钟", "higher"),
                ("日均总睡眠", "小时", "higher"),
                ("日均静息心率", "bpm", "lower"),
                ("心率变异性 HRV", "ms", "higher"),
                ("体重", "kg", "neutral"),
            ]
            cards = []
            for idx_s, (mlabel, munit, polarity) in enumerate(spark_specs):
                pts = []
                for y in years:
                    cell = yt.get(y, {}).get(mlabel)
                    if cell and cell.get("avg") is not None:
                        pts.append((y, cell["avg"], int(cell.get("days", 0))))
                    else:
                        pts.append((y, None, 0))
                valid_pts = [p for p in pts if p[1] is not None]
                if not valid_pts:
                    continue

                first_v = valid_pts[0][1]
                last_y, last_v, _ = valid_pts[-1]
                pct = ((last_v - first_v) / abs(first_v) * 100.0) if (len(valid_pts) >= 2 and first_v) else 0.0

                if polarity == "higher":
                    if pct >= 5:
                        color, delta_cls, arrow = "#047857", "wd-good", "↗"
                    elif pct <= -5:
                        color, delta_cls, arrow = "#b45309", "wd-warn", "↘"
                    else:
                        color, delta_cls, arrow = "#134e4a", "wd-flat", "→"
                elif polarity == "lower":
                    if pct <= -3:
                        color, delta_cls, arrow = "#047857", "wd-good", "↘"
                    elif pct >= 3:
                        color, delta_cls, arrow = "#b45309", "wd-warn", "↗"
                    else:
                        color, delta_cls, arrow = "#134e4a", "wd-flat", "→"
                else:
                    color, delta_cls, arrow = "#134e4a", "wd-flat", ("↗" if pct >= 2 else ("↘" if pct <= -2 else "→"))

                sign = "+" if pct > 0 else ""
                delta_badge = (
                    f'<span class="w-delta {delta_cls}">{sign}{round(pct)}% {arrow}</span>'
                    if len(valid_pts) >= 2
                    else ""
                )
                last_disp = f"{int(last_v)}" if isinstance(last_v, int) or float(last_v).is_integer() else f"{last_v}"
                svg_html = _render_sparkline_svg(years, pts, color, f"m{idx_s}")
                cards.append(f"""
                <div class="w-spark-card">
                  <div class="w-spark-top">
                    <span class="w-spark-name">{_esc(mlabel)}</span>
                    {delta_badge}
                  </div>
                  <div class="w-spark-val"><strong>{_esc(last_disp)}</strong> <span>{_esc(munit)}</span><em>{_esc(last_y)}均值</em></div>
                  {svg_html}
                </div>""")

            if cards:
                spark_grid_html = f"""
                <div class="w-table-title">近 4 年穿戴核心趋势图（空心圆点表示该年样本少于 30 天）</div>
                <div class="w-spark-grid">{"".join(cards)}</div>"""

        wearable_section_html = f"""
  <h2 class="section-title">穿戴印证 · Apple Watch 多年行为趋势与体检交叉解读</h2>
  <div class="w-card">
    <div class="w-meta">{_esc(span_txt)}</div>
    {wi_headline}
    {wi_cross}
    {wi_action}
    {spark_grid_html}
    {pills_html}
  </div>"""

    # 7. Full System Indicator Tables (Deterministic from Mirobody v_observation)
    table_sections = []
    for sb in mined_data["systems"]:
        badges = []
        if sb["red_count"] > 0:
            badges.append(f'<span class="mini-badge mb-red">{sb["red_count"]} 项异常</span>')
        if sb["yellow_count"] > 0:
            badges.append(f'<span class="mini-badge mb-yellow">{sb["yellow_count"]} 项临界</span>')
        if not badges:
            badges.append('<span class="mini-badge mb-green">全部平稳</span>')

        rows = []
        for item in sb["items"]:
            lvl = item["risk_level"]
            if lvl == "red":
                st_cell = f'<span class="cell-tag tag-red">{_esc(item["direction"] or "异常")}</span>'
                row_cls = "row-red"
            elif lvl == "yellow":
                st_cell = f'<span class="cell-tag tag-yellow">{_esc(item["direction"] or "临界")}</span>'
                row_cls = "row-yellow"
            elif lvl == "info":
                st_cell = '<span class="cell-tag tag-info">记录</span>'
                row_cls = ""
            else:
                st_cell = '<span class="cell-tag tag-normal">正常</span>'
                row_cls = ""

            val_disp = f"{item['value_text']} {item['unit']}".strip()
            loinc_disp = f'<span class="loinc-code">{_esc(item["loinc_code"])}</span>' if item["loinc_code"] else ""
            rows.append(f"""
              <tr class="{row_cls}">
                <td class="col-date">{_esc(item["report_date"])}</td>
                <td class="col-name">{_esc(item["name"])} {loinc_disp}</td>
                <td class="col-val"><strong>{_esc(val_disp)}</strong></td>
                <td class="col-ref">{_esc(item["ref_text"] or "—")}</td>
                <td class="col-st">{st_cell}</td>
              </tr>""")

        table_sections.append(f"""
        <details class="sys-details">
          <summary>
            <span class="sum-title">{_esc(sb["system"])}（共 {sb["total_count"]} 项）</span>
            <span class="sum-badges">{"".join(badges)}</span>
          </summary>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>日期</th>
                  <th>检查项目 (LOINC)</th>
                  <th>实测结果</th>
                  <th>参考区间</th>
                  <th>三层评估</th>
                </tr>
              </thead>
              <tbody>{"".join(rows)}</tbody>
            </table>
          </div>
        </details>""")
    tables_html = "\n".join(table_sections)

    disclaimer = report_json.get(
        "disclaimer",
        "本报告基于已上传体检数据由 AI 辅助整理，仅作健康风险科普、日常药食同源膳食与复查沟通参考，不构成医疗诊断、处方或用药依据。异常指标请及时前往正规医疗机构遵医嘱复查。"
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{_esc(title)}</title>
<style>
  :root {{
    --bg: #f6f4ef;
    --card: #ffffff;
    --ink: #1f2933;
    --muted: #5b6770;
    --brand: #134e4a;
    --brand-light: #e6f4f1;
    --red: #b91c1c;
    --red-bg: #fef2f2;
    --red-bd: #fecaca;
    --yellow: #b45309;
    --yellow-bg: #fffbeb;
    --yellow-bd: #fde68a;
    --green: #047857;
    --green-bg: #ecfdf5;
    --green-bd: #a7f3d0;
    --border: #e5e1d8;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    line-height: 1.65;
    -webkit-font-smoothing: antialiased;
  }}
  .page {{
    max-width: 860px;
    margin: 0 auto;
    padding: 20px 16px 64px;
  }}
  .toolbar {{
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-bottom: 12px;
  }}
  .btn-print {{
    background: var(--brand);
    color: #fff;
    border: none;
    border-radius: 999px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
  }}
  .btn-print:hover {{ opacity: 0.92; }}
  .hero {{
    background: linear-gradient(135deg, #0f3d3a 0%, #165b55 100%);
    color: #fff;
    border-radius: 20px;
    padding: 28px 26px 24px;
    box-shadow: 0 12px 30px rgba(15, 61, 58, 0.14);
  }}
  .hero-kicker {{
    font-size: 12px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    opacity: 0.82;
    margin-bottom: 6px;
  }}
  .hero h1 {{
    margin: 0 0 10px;
    font-size: 24px;
    line-height: 1.3;
    font-weight: 700;
  }}
  .hero-meta {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px 20px;
    font-size: 13px;
    opacity: 0.9;
    margin-bottom: 18px;
  }}
  .stats-strip {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 14px;
    padding: 12px;
  }}
  .stat-box {{ text-align: center; }}
  .stat-num {{ font-size: 22px; font-weight: 700; line-height: 1.2; }}
  .stat-lbl {{ font-size: 11px; opacity: 0.85; margin-top: 2px; }}
  .exec-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 20px 22px;
    margin-top: 16px;
  }}
  .silent-callout {{
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-left: 4px solid #d97706;
    border-radius: 12px;
    padding: 12px 16px;
    margin-top: 12px;
    font-size: 13.5px;
    color: #78350f;
    line-height: 1.6;
  }}
  .silent-callout strong {{ color: #92400e; }}
  .exec-top {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 10px;
  }}
  .grade-badge {{
    display: inline-block;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 700;
    color: {grade_fg};
    background: {grade_bg};
    border: 1px solid {grade_bd};
  }}
  .exec-sub {{
    display: inline-block;
    margin-left: 8px;
    font-size: 12px;
    font-weight: 500;
    color: var(--muted);
  }}
  .exec-verdict {{
    font-size: 15px;
    font-weight: 700;
    color: var(--ink);
    background: #f8f7f3;
    border-radius: 10px;
    padding: 10px 13px;
    margin-bottom: 12px;
    line-height: 1.55;
  }}
  .exec-sec {{
    border-radius: 12px;
    padding: 13px 15px;
    margin-bottom: 10px;
    border: 1px solid var(--border);
  }}
  .exec-sec:last-child {{ margin-bottom: 0; }}
  .exec-good {{ background: #f3fbf7; border-color: var(--green-bd); border-left: 4px solid var(--green); }}
  .exec-watch {{ background: #fffbf6; border-color: #fed7aa; border-left: 4px solid #ea580c; }}
  .exec-step {{ background: #f0f9f7; border-color: #99f6e4; border-left: 4px solid var(--brand); }}
  .exec-sec-title {{
    font-size: 13.5px;
    font-weight: 800;
    color: var(--ink);
    margin-bottom: 6px;
  }}
  .exec-good .exec-sec-title {{ color: var(--green); }}
  .exec-watch .exec-sec-title {{ color: #c2410c; }}
  .exec-step .exec-sec-title {{ color: var(--brand); }}
  .exec-sec-p {{
    margin: 0 0 8px;
    font-size: 14px;
    line-height: 1.6;
    color: var(--ink);
  }}
  .exec-watch-list {{
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .exec-watch-item {{
    background: #ffffff;
    border: 1px solid #f3e8dc;
    border-radius: 10px;
    padding: 11px 13px;
  }}
  .ew-head {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 5px;
  }}
  .ew-num {{
    width: 20px;
    height: 20px;
    border-radius: 999px;
    font-size: 11.5px;
    font-weight: 800;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    color: #fff;
  }}
  .ew-num-red {{ background: var(--red); }}
  .ew-num-yellow {{ background: #d97706; }}
  .ew-title {{ font-size: 14.5px; font-weight: 700; color: var(--ink); line-height: 1.35; }}
  .ew-explain {{ margin: 0 0 8px; font-size: 13.5px; color: #374151; line-height: 1.6; }}
  .exec-metrics {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }}
  .em-chip {{
    background: #ffffff;
    border: 1px solid var(--border);
    border-radius: 9px;
    padding: 8px 10px;
    font-size: 12.5px;
    line-height: 1.45;
  }}
  .em-good {{ background: #ffffff; border-color: var(--green-bd); }}
  .em-red {{ background: #fff9f9; border-color: var(--red-bd); }}
  .em-yellow {{ background: #fffdf5; border-color: var(--yellow-bd); }}
  .em-top {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 6px;
    margin-bottom: 3px;
  }}
  .em-name {{ color: var(--ink); font-size: 12.5px; }}
  .em-term {{ color: var(--muted); font-weight: 400; font-size: 11.5px; }}
  .em-status {{
    font-size: 11px;
    font-weight: 700;
    padding: 1px 7px;
    border-radius: 999px;
    white-space: nowrap;
    flex-shrink: 0;
  }}
  .em-good .em-status {{ background: var(--green-bg); color: var(--green); }}
  .em-red .em-status {{ background: var(--red-bg); color: var(--red); }}
  .em-yellow .em-status {{ background: var(--yellow-bg); color: var(--yellow); }}
  .em-vals {{
    display: flex;
    flex-wrap: wrap;
    gap: 4px 10px;
    font-size: 12px;
    color: #374151;
    font-variant-numeric: tabular-nums;
  }}
  .em-ref {{ color: var(--muted); }}
  .section-title {{
    margin: 28px 0 12px;
    font-size: 18px;
    font-weight: 700;
    color: var(--brand);
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .section-title::before {{
    content: "";
    width: 4px;
    height: 18px;
    border-radius: 2px;
    background: var(--brand);
    display: inline-block;
  }}
  .pain-card {{
    background: var(--card);
    border-radius: 16px;
    padding: 20px 22px;
    margin-bottom: 14px;
    border: 1px solid var(--border);
    border-left: 5px solid var(--yellow);
  }}
  .pain-card.sev-red {{ border-left-color: var(--red); }}
  .pain-badge {{
    display: inline-block;
    font-size: 12px;
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 999px;
    margin-bottom: 6px;
    background: var(--yellow-bg);
    color: var(--yellow);
  }}
  .sev-red .pain-badge {{ background: var(--red-bg); color: var(--red); }}
  .pain-title {{ margin: 0 0 10px; font-size: 17px; color: var(--ink); }}
  .pain-pills {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }}
  .ind-pill {{
    background: #f3f4f6;
    color: #111827;
    font-size: 12px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 6px;
  }}
  .pain-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 12px;
  }}
  .pain-block {{
    background: #faf9f6;
    border-radius: 10px;
    padding: 12px 14px;
    font-size: 14px;
  }}
  .pain-warn-box {{ background: #fff8f6; border: 1px solid #fee2e2; }}
  .pain-label {{ font-size: 12px; font-weight: 700; color: var(--muted); margin-bottom: 4px; }}
  .pain-block p {{ margin: 0; }}
  .pain-action {{
    background: var(--brand-light);
    color: var(--brand);
    padding: 10px 14px;
    border-radius: 10px;
    font-size: 14px;
  }}
  .prot-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 12px;
  }}
  .prot-card {{
    background: var(--card);
    border: 1px solid var(--green-bd);
    border-radius: 14px;
    padding: 14px 16px;
  }}
  .prot-top {{ display: flex; align-items: center; gap: 7px; margin-bottom: 6px; }}
  .prot-dot {{ width: 8px; height: 8px; border-radius: 50%; background: var(--green); flex-shrink: 0; }}
  .prot-title {{ font-weight: 700; font-size: 14px; line-height: 1.35; }}
  .prot-val-row {{ margin-bottom: 7px; }}
  .prot-val {{ display: inline-block; font-size: 12px; font-weight: 700; color: var(--green); background: var(--green-bg); padding: 2px 9px; border-radius: 999px; }}
  .prot-meaning {{ font-size: 13px; color: var(--muted); }}
  .sys-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 10px;
  }}
  .sys-summary-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-left: 4px solid var(--green);
    border-radius: 12px;
    padding: 12px 14px;
  }}
  .sys-summary-card.st-red {{ border-left-color: var(--red); }}
  .sys-summary-card.st-yellow {{ border-left-color: var(--yellow); }}
  .sys-summary-card.st-green {{ border-left-color: var(--green); }}
  .sys-summary-head {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px; }}
  .sys-summary-name {{ font-weight: 700; font-size: 14.5px; }}
  .sys-pill {{ font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }}
  .sys-pill.st-red {{ background: var(--red-bg); color: var(--red); }}
  .sys-pill.st-yellow {{ background: var(--yellow-bg); color: var(--yellow); }}
  .sys-pill.st-green {{ background: var(--green-bg); color: var(--green); }}
  .sys-headline {{ font-weight: 500; font-size: 13.5px; color: var(--ink); line-height: 1.5; }}
  .ft-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 18px 20px;
    margin-bottom: 12px;
  }}
  .ft-head {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
  .ft-head h4 {{ margin: 0; font-size: 16px; }}
  .ft-badge {{ font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: 999px; }}
  .ft-red {{ background: var(--red-bg); color: var(--red); border: 1px solid var(--red-bd); }}
  .ft-yellow {{ background: var(--yellow-bg); color: var(--yellow); border: 1px solid var(--yellow-bd); }}
  .ft-green {{ background: var(--green-bg); color: var(--green); border: 1px solid var(--green-bd); }}
  .ft-body {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .ft-avoid {{ background: var(--red-bg); border: 1px solid var(--red-bd); border-radius: 12px; padding: 12px 14px; font-size: 14px; }}
  .ft-rec {{ background: var(--green-bg); border: 1px solid var(--green-bd); border-radius: 12px; padding: 12px 14px; font-size: 14px; }}
  .ft-sub-title {{ font-size: 12px; font-weight: 700; margin-bottom: 6px; }}
  .avoid-t {{ color: var(--red); }}
  .rec-t {{ color: var(--green); }}
  .ft-avoid p, .ft-rec p {{ margin: 0; }}
  .doc-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px 18px;
    margin-bottom: 10px;
  }}
  .doc-top {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }}
  .doc-num {{ background: var(--brand); color: #fff; font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 6px; }}
  .doc-dept {{ font-size: 12px; font-weight: 600; color: var(--brand); background: var(--brand-light); padding: 2px 10px; border-radius: 999px; }}
  .doc-q {{ font-size: 15px; font-weight: 700; color: var(--ink); margin-bottom: 4px; }}
  .doc-why {{ font-size: 13px; color: var(--muted); }}
  .rc-list {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 8px 18px; }}
  .rc-item {{ display: flex; gap: 16px; padding: 14px 0; border-bottom: 1px dashed var(--border); }}
  .rc-item:last-child {{ border-bottom: none; }}
  .rc-time {{ min-width: 110px; font-weight: 700; color: var(--brand); font-size: 14px; }}
  .rc-items {{ font-weight: 600; font-size: 14px; margin-bottom: 2px; }}
  .rc-goal {{ font-size: 13px; color: var(--muted); }}
  .sys-details {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    margin-bottom: 10px;
    overflow: hidden;
  }}
  .sys-details summary {{
    cursor: pointer;
    padding: 13px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 700;
    font-size: 14px;
    background: #faf9f6;
  }}
  .sum-badges {{ display: flex; gap: 6px; }}
  .mini-badge {{ font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; }}
  .mb-red {{ background: var(--red-bg); color: var(--red); }}
  .mb-yellow {{ background: var(--yellow-bg); color: var(--yellow); }}
  .mb-green {{ background: var(--green-bg); color: var(--green); }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ padding: 9px 12px; text-align: left; border-top: 1px solid #f0ede6; }}
  th {{ color: var(--muted); font-weight: 600; background: #fff; font-size: 12px; }}
  tr.row-red {{ background: #fff7f7; }}
  tr.row-yellow {{ background: #fffdf5; }}
  .loinc-code {{ font-size: 11px; color: #8c96a0; margin-left: 4px; font-family: ui-monospace, monospace; }}
  .cell-tag {{ font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }}
  .tag-red {{ background: var(--red-bg); color: var(--red); }}
  .tag-yellow {{ background: var(--yellow-bg); color: var(--yellow); }}
  .tag-normal {{ background: var(--green-bg); color: var(--green); }}
  .tag-info {{ background: #f3f4f6; color: #6b7280; }}
  .raw-master-details {{
    margin-top: 28px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
  }}
  .raw-master-details > summary {{
    cursor: pointer;
    list-style: none;
    padding: 16px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    background: #faf9f6;
    font-weight: 700;
    color: var(--brand);
    font-size: 16px;
  }}
  .raw-master-details > summary::-webkit-details-marker {{ display: none; }}
  .raw-master-hint {{
    font-size: 12.5px;
    font-weight: 600;
    color: var(--brand);
    background: var(--brand-light);
    padding: 4px 12px;
    border-radius: 999px;
  }}
  .raw-master-details[open] .raw-master-hint::before {{ content: "▲ 收起底表 · "; }}
  .raw-master-details:not([open]) .raw-master-hint::before {{ content: "▼ 点击展开 · "; }}
  .raw-master-body {{
    padding: 14px 16px 8px;
    border-top: 1px solid var(--border);
  }}
  .disclaimer {{
    margin-top: 28px;
    background: #efede7;
    border-radius: 12px;
    padding: 14px 16px;
    font-size: 12px;
    color: var(--muted);
  }}
  .hero-note {{
    margin-top: 10px;
    padding: 8px 12px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.14);
    font-size: 13px;
    color: #f0fdfa;
    line-height: 1.5;
  }}
  .w-card {{
    background: var(--card);
    border: 1px solid #cce3de;
    border-left: 5px solid var(--brand);
    border-radius: 16px;
    padding: 18px 20px;
    box-shadow: 0 6px 18px rgba(19, 78, 74, 0.05);
  }}
  .w-meta {{ font-size: 12px; color: var(--muted); margin-bottom: 6px; }}
  .w-headline {{ font-size: 16px; font-weight: 800; color: var(--brand); margin-bottom: 8px; }}
  .w-cross {{ margin: 0 0 12px; font-size: 14px; color: var(--ink); line-height: 1.65; }}
  .w-action {{
    margin: 0 0 14px;
    padding: 11px 14px;
    border-radius: 12px;
    background: #ecfdf5;
    border: 1.5px solid #6ee7b7;
    color: #064e3b;
    font-size: 14.5px;
    font-weight: 600;
    line-height: 1.55;
  }}
  .w-action strong {{ color: #047857; font-weight: 800; }}
  .section-sub {{ margin: -8px 0 14px; font-size: 13px; color: var(--muted); }}
  .w-table-title {{ font-size: 12px; font-weight: 700; color: var(--muted); margin: 4px 0 10px; }}
  .w-spark-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 14px; }}
  .w-spark-card {{
    background: #faf9f6;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 11px 12px 8px;
  }}
  .w-spark-top {{ display: flex; justify-content: space-between; align-items: center; gap: 6px; margin-bottom: 4px; }}
  .w-spark-name {{ font-size: 12.5px; font-weight: 700; color: var(--ink); }}
  .w-delta {{ font-size: 11px; font-weight: 700; padding: 1px 7px; border-radius: 999px; white-space: nowrap; }}
  .wd-good {{ background: var(--green-bg); color: var(--green); }}
  .wd-warn {{ background: var(--yellow-bg); color: var(--yellow); }}
  .wd-red {{ background: var(--red-bg); color: var(--red); }}
  .wd-flat {{ background: #eef2f3; color: #4b5563; }}
  .lab-spark-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; margin-bottom: 10px; }}
  .lab-spark-card {{
    background: #fcfbf8;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 10px 12px 6px;
  }}
  .w-spark-val {{ display: flex; align-items: baseline; gap: 4px; margin-bottom: 2px; }}
  .w-spark-val strong {{ font-size: 19px; font-weight: 800; color: var(--ink); font-variant-numeric: tabular-nums; }}
  .w-spark-val span {{ font-size: 12px; color: var(--muted); }}
  .w-spark-val em {{ font-style: normal; font-size: 11px; color: #8c96a0; margin-left: auto; }}
  .w-svg {{ display: block; overflow: visible; }}
  .w-cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
  .w-col {{ border-radius: 12px; padding: 10px 13px; font-size: 12.5px; line-height: 1.55; }}
  .w-col-green {{ background: var(--green-bg); border: 1px solid var(--green-bd); color: #064e3b; }}
  .w-col-amber {{ background: var(--yellow-bg); border: 1px solid var(--yellow-bd); color: #78350f; }}
  .w-col-t {{ font-weight: 700; margin-bottom: 5px; font-size: 12.5px; }}
  .w-col ul {{ margin: 0; padding-left: 16px; }}
  .w-col li {{ margin-bottom: 3px; }}
  .w-col li:last-child {{ margin-bottom: 0; }}
  @media (max-width: 720px) {{
    .w-spark-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .w-cols {{ grid-template-columns: 1fr; }}
  }}
  @media (max-width: 440px) {{
    .w-spark-grid {{ grid-template-columns: 1fr; }}
  }}
  @media (max-width: 680px) {{
    .stats-strip {{ grid-template-columns: repeat(2, 1fr); }}
    .exec-metrics, .pain-grid, .ft-body {{ grid-template-columns: 1fr; }}
    .rc-item {{ flex-direction: column; gap: 4px; }}
  }}
  @media print {{
    body {{ background: #fff; }}
    .toolbar {{ display: none; }}
    .page {{ max-width: 100%; padding: 0; }}
    .hero, .exec-sec, .em-chip {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head>
<body>
<div class="page">
  <div class="toolbar">
    <button class="btn-print" onclick="window.print()">打印 / 导出 PDF 报告</button>
  </div>

  <div class="hero">
    <div class="hero-kicker">MIROBODY DATA HUB × DEEPSEEK-FLASH PROACTIVE RISK ENGINE</div>
    <h1>{_esc(title)}</h1>
    <div class="hero-meta">
      <span>档案对象：{_esc(user_label)}</span>
      {profile_badge_html}
      <span>体检数据跨度：{_esc(date_span)}</span>
      <span>生成时间：{generated_at}</span>
    </div>
    {recent_note_html}
    <div class="stats-strip">
      <div class="stat-box"><div class="stat-num">{stats["total_observations"]}</div><div class="stat-lbl">标准化入库指标</div></div>
      <div class="stat-box"><div class="stat-num" style="color:#fca5a5;">{stats["red_count"]}</div><div class="stat-lbl">🔴 显性异常红牌</div></div>
      <div class="stat-box"><div class="stat-num" style="color:#fde68a;">{stats["yellow_count"]}</div><div class="stat-lbl">🟡 隐性临界黄牌</div></div>
      <div class="stat-box"><div class="stat-num">{stats["file_count"]}</div><div class="stat-lbl">溯源体检原件</div></div>
    </div>
  </div>

  <div class="exec-card">
    <div class="exec-top">
      <div>
        <strong style="font-size:15.5px;">一屏核心结论</strong>
        <span class="exec-sub">不用查词典，15 秒看懂体检重点</span>
      </div>
      <span class="grade-badge">综合评定：{_esc(grade)}</span>
    </div>
    {exec_body_html}
  </div>
  {silent_callout_html}

  <h2 class="section-title">一、核心风险串联排雷（按优先级排序）</h2>
  <div class="section-sub">把分散在各科室的关联异常串成因果链：看懂为什么不能只看单项、放任不管会怎样、当下最该先抓什么</div>
  {pain_html}

  <h2 class="section-title">二、值得肯定的健康保护亮点</h2>
  <div class="prot-grid">{prot_html}</div>
  {wearable_section_html}
  {sys_summary_section_html}

  <h2 class="section-title">四、分品类滋补与药食同源红绿灯清单（先排雷 · 再调理）</h2>
  {ft_html}

  <h2 class="section-title">五、下次复查直接照着问医生的精准清单</h2>
  {doc_html}

  <h2 class="section-title">六、复查倒计时与闭环验证计划</h2>
  <div class="rc-list">{recheck_html}</div>

  <details class="raw-master-details">
    <summary>
      <span>七、Mirobody 标准化全量指标底表（含 LOINC 编码与三层标注）</span>
      <span class="raw-master-hint">共 {stats["total_observations"]} 项（🔴 {stats["red_count"]} / 🟡 {stats["yellow_count"]}）</span>
    </summary>
    <div class="raw-master-body">
      {tables_html}
    </div>
  </details>

  <div class="disclaimer">
    <strong>合规与健康声明：</strong>{_esc(disclaimer)}
  </div>
</div>
</body>
</html>
"""
