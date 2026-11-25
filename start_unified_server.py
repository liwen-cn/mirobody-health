#!/usr/bin/env python3
"""Unified Gateway & Health Report Studio for Mirobody.

Listens on http://127.0.0.1:18060.
- Seamlessly proxies Mirobody requests to internal port (18061).
- Injects a native '健康报告' sidebar navigation button into Mirobody.
- Clicking '健康报告' smoothly replaces the main page area with the Report Studio workspace.
- Supports generating new reports, viewing history, and exporting mobile HD long-PNG and mobile PDF.
"""

import html
import http.client
import json
import os
import re
import select
import socket
import socketserver
import sys
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from generate_from_mirobody import run_pipeline
from src.exporter import export_mobile_pdf, export_mobile_png
from src.mirobody_reader import list_users_with_uploads

HOST = os.environ.get("GATEWAY_BIND", "127.0.0.1")
PORT = int(os.environ.get("GATEWAY_PORT", "18060"))
BACKEND_HOST = os.environ.get("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "18061"))

OUTPUT_DIR = "output"

CONSTITUTION_TAGS = [
    "餐后易困乏力",
    "熬夜/作息不规律",
    "应酬/饮食偏油",
    "畏寒怕冷",
    "口苦易上火",
    "睡眠浅易醒",
    "肠胃偏弱",
]

INJECT_JS = """
<script id="mirobody-report-integration">
(function() {
  console.log('[Mirobody Integration] Health Report script loaded');
  if (window.__mirobody_report_injected) return;
  window.__mirobody_report_injected = true;

  var currentViewIsReport = false;
  var reportFrame = null;

  function ensureReportFrame() {
    if (reportFrame && document.body.contains(reportFrame)) return reportFrame;
    reportFrame = document.createElement('iframe');
    reportFrame.id = 'mirobody-report-view';
    reportFrame.src = '/studio/view';
    // Use high z-index and solid opaque background with !important so it completely covers the main content area
    reportFrame.style.cssText = 'position:fixed !important; top:0 !important; right:0 !important; bottom:0 !important; border:none !important; z-index:99999 !important; background:#f6f4ef !important; opacity:1 !important; width:calc(100vw - 272px) !important; height:100vh !important; display:none; box-sizing:border-box !important;';
    document.body.appendChild(reportFrame);
    return reportFrame;
  }

  function updateFramePosition() {
    if (!reportFrame) return;
    var sidebar = document.querySelector('[class*="_sidebar_"]') || document.querySelector('nav') || document.querySelector('aside');
    if (sidebar) {
      var w = sidebar.getBoundingClientRect().width;
      if (w > 0) {
        reportFrame.style.setProperty('left', w + 'px', 'important');
        reportFrame.style.setProperty('width', 'calc(100vw - ' + w + 'px)', 'important');
        reportFrame.style.setProperty('height', '100vh', 'important');
      }
    }
  }

  function getNativeContent() {
    return document.querySelector('[class*="_content_wrapper_"]') ||
           document.querySelector('[class*="_chat_"] > div:last-child') ||
           document.querySelector('main');
  }

  function showReportView() {
    currentViewIsReport = true;
    var frame = ensureReportFrame();
    updateFramePosition();
    frame.style.setProperty('display', 'block', 'important');

    var nativeContent = getNativeContent();
    if (nativeContent) {
      nativeContent.style.setProperty('visibility', 'hidden', 'important');
    }

    var allNavs = document.querySelectorAll('button[data-tour], [class*="_nav_item_"]');
    allNavs.forEach(function(el) {
      el.removeAttribute('aria-current');
      el.classList.forEach(function(c) {
        if (c.indexOf('active') !== -1) el.classList.remove(c);
      });
    });

    var rBtn = document.getElementById('nav-item-report');
    if (rBtn) {
      rBtn.setAttribute('aria-current', 'page');
      var sib = document.querySelector('[class*="_nav_item_"]');
      if (sib) {
        var baseCls = Array.from(sib.classList).find(function(c) { return c.indexOf('_nav_item_uibb6_') !== -1; });
        if (baseCls) {
          rBtn.classList.add(baseCls.replace('_nav_item_uibb6_', '_nav_item_active_uibb6_'));
        }
      }
      rBtn.style.backgroundColor = 'var(--color-accent-soft, #e6f4f1)';
      rBtn.style.color = 'var(--color-accent, #134e4a)';
    }
  }

  function hideReportView() {
    currentViewIsReport = false;
    if (reportFrame) {
      reportFrame.style.setProperty('display', 'none', 'important');
    }
    var nativeContent = getNativeContent();
    if (nativeContent) {
      nativeContent.style.visibility = '';
    }
    var rBtn = document.getElementById('nav-item-report');
    if (rBtn) {
      rBtn.removeAttribute('aria-current');
      rBtn.style.backgroundColor = '';
      rBtn.style.color = '';
    }
  }

  function injectSidebarButton() {
    if (document.getElementById('nav-item-report')) return;

    // 1. Try finding by tour attributes
    var dataBtn = document.querySelector('[data-tour="sidebar-data"]') || document.querySelector('[data-tour="sidebar-indicators"]');
    var container = dataBtn ? dataBtn.parentElement : null;

    if (!container) {
      container = document.querySelector('[class*="_section_"]');
      if (container) {
        dataBtn = container.querySelector('button');
      }
    }

    if (!container || !dataBtn) return;

    console.log('[Mirobody Integration] Found sidebar container, injecting report button...');

    var reportBtn = document.createElement('button');
    reportBtn.type = 'button';
    reportBtn.id = 'nav-item-report';
    reportBtn.className = dataBtn.className;
    reportBtn.setAttribute('data-tour', 'sidebar-health-report');
    reportBtn.title = '健康报告';

    var activeCls = Array.from(reportBtn.classList).find(function(c) { return c.indexOf('active') !== -1; });
    if (activeCls) reportBtn.classList.remove(activeCls);

    reportBtn.innerHTML = `
      <svg class="_nav_icon_uibb6_123" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0; margin-right:4px;">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <line x1="8" y1="13" x2="16" y2="13"></line>
        <line x1="8" y1="17" x2="13" y2="17"></line>
        <polyline points="9 9 10 9 10 10"></polyline>
      </svg>
      <span>健康报告</span>
    `;

    reportBtn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      showReportView();
    });

    var indBtn = container.querySelector('[data-tour="sidebar-indicators"]');
    if (indBtn && indBtn.nextSibling) {
      container.insertBefore(reportBtn, indBtn.nextSibling);
    } else {
      container.appendChild(reportBtn);
    }
    console.log('[Mirobody Integration] Injected successfully!');
  }

  document.addEventListener('click', function(e) {
    var target = e.target;
    var nav = target.closest('button');
    if (nav && nav.id !== 'nav-item-report' && (nav.hasAttribute('data-tour') || (nav.className && nav.className.indexOf('_nav_item_') !== -1))) {
      hideReportView();
    }
  }, true);

  var observer = new MutationObserver(function() {
    injectSidebarButton();
    updateFramePosition();
  });
  if (document.body) {
    observer.observe(document.body, { childList: true, subtree: true });
  } else {
    document.addEventListener('DOMContentLoaded', function() {
      observer.observe(document.body, { childList: true, subtree: true });
    });
  }

  setInterval(function() {
    injectSidebarButton();
    updateFramePosition();
  }, 500);

  window.addEventListener('resize', updateFramePosition);
})();
</script>"""

def _grade_badge_style(grade):
    """Return (text_color, bg_color, border_color) for a report overall_grade badge."""
    g = str(grade or "")
    if "尽快" in g or "就医" in g:
        return ("#991b1b", "#fef2f2", "#fecaca")
    if "重点" in g:
        return ("#b45309", "#fffbeb", "#fde68a")
    if "轻度" in g:
        return ("#1d4ed8", "#eff6ff", "#bfdbfe")
    return ("#065f46", "#ecfdf5", "#a7f3d0")


def _parse_report_card_meta(fname, users_by_id=None):
    base = fname[:-5]
    m = re.search(r"_u([^_]+)_(\d{8})_(\d{6})$", base)
    uid = m.group(1) if m else ""
    if m:
        dt = datetime.strptime(m.group(2) + m.group(3), "%Y%m%d%H%M%S")
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H:%M")
    else:
        mtime = os.path.getmtime(os.path.join(OUTPUT_DIR, fname))
        dt = datetime.fromtimestamp(mtime)
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H:%M")

    db_user = (users_by_id or {}).get(uid) or {}
    person_name = db_user.get("display_name") or (f"用户 #{uid}" if uid else "健康档案")
    default_bits = [b for b in (db_user.get("gender"), f"{db_user['age']}岁" if db_user.get("age") else "") if b]
    person_meta = " · ".join(default_bits)
    checkup_text = ""
    grade = ""
    top_risk = ""
    extra_risk_count = 0
    stats_text = ""
    context_tags = []

    json_path = os.path.join(OUTPUT_DIR, base + ".json")
    if os.path.isfile(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            user_profile = data.get("user_profile") or {}
            ms = data.get("mined_summary") or {}
            wearable = data.get("wearable_summary") or {}
            rep = data.get("report") or {}

            generic_labels = {"", "家庭主档案", "个人健康主档案", "家庭健康档案"}
            raw_label = (user_profile.get("code_name") or "").strip()
            cleaned_label = re.sub(r"报告$", "", raw_label).strip()
            if raw_label not in generic_labels and cleaned_label:
                person_name = cleaned_label
            elif db_user.get("display_name"):
                person_name = db_user["display_name"]
            else:
                person_name = f"用户 #{uid}" if uid else "健康档案"

            g = (user_profile.get("gender") or db_user.get("gender") or "").strip()
            a = user_profile.get("age") if user_profile.get("age") is not None else db_user.get("age")
            meta_bits = [b for b in (g, f"{a}岁" if a else "") if b]
            person_meta = " · ".join(meta_bits)

            report_dates = sorted([str(d) for d in (ms.get("report_dates") or []) if d])
            span = f"{report_dates[0]} ~ {report_dates[-1]}" if len(report_dates) > 1 else (report_dates[0] if report_dates else "")
            fc = ms.get("file_count") or 0
            if span and fc:
                checkup_text = f"{span}（{fc}份原件）"
            elif span:
                checkup_text = span
            elif fc:
                checkup_text = f"{fc}份原件"

            pain_points = rep.get("core_pain_points") or []
            if pain_points and isinstance(pain_points[0], dict):
                top_risk = (pain_points[0].get("title") or "").strip()
            extra_risk_count = max(len(pain_points) - 1, 0)

            if ms.get("total_observations"):
                stats_text = f"{ms['total_observations']} 项 · 🔴 {ms.get('red_count', 0)} · 🟡 {ms.get('yellow_count', 0)}"
                if (ms.get("trend_alert_count") or 0) > 0:
                    stats_text += f" · 📈 {ms['trend_alert_count']} 趋势"

            if wearable.get("has_data"):
                context_tags.append("⌚ 含穿戴数据")
            for t in (user_profile.get("constitution_tags") or [])[:3]:
                if t and str(t).strip():
                    context_tags.append(str(t).strip())

            if rep.get("overall_grade"):
                grade = rep["overall_grade"]
        except Exception:
            pass

    return {
        "fname": fname,
        "person_name": person_name,
        "person_meta": person_meta,
        "date_str": date_str,
        "time_str": time_str,
        "checkup_text": checkup_text,
        "grade": grade,
        "top_risk": top_risk,
        "extra_risk_count": extra_risk_count,
        "stats_text": stats_text,
        "context_tags": context_tags,
    }


def _render_studio_html(error_msg="", is_standalone=False):
    try:
        users = list_users_with_uploads()
    except Exception as e:
        users = []
        error_msg = error_msg or f"连接 Mirobody 数据库失败：{e}"

    users_by_id = {str(u["user_id"]): u for u in users}

    user_options = []
    for u in users:
        uid = str(u["user_id"])
        display_name = u.get("display_name") or f"用户 #{uid}"
        meta_bits = [b for b in (u.get("gender"), f"{u['age']}岁" if u.get("age") else "") if b]
        suffix = f"（{' · '.join(meta_bits)}）" if meta_bits else ""
        txt = f"{display_name}{suffix} — {u['obs_count']} 项指标 / {u['file_count']} 份原件 ({u['first_date']} ~ {u['last_date']})"
        g_attr = html.escape(u.get("gender") or "")
        a_attr = html.escape(str(u["age"])) if u.get("age") else ""
        n_attr = html.escape(display_name)
        user_options.append(
            f'<option value="{html.escape(uid)}" data-name="{n_attr}" data-gender="{g_attr}" data-age="{a_attr}">{html.escape(txt)}</option>'
        )
    if not user_options:
        user_options.append('<option value="1" data-name="家庭主档案" data-gender="" data-age="">暂无已解析报告（请先在 Mirobody 上传体检报告）</option>')

    default_label = users[0].get("display_name") if users else "家庭主档案"

    tag_checks = []
    for tag in CONSTITUTION_TAGS:
        t_esc = html.escape(tag)
        tag_checks.append(
            f'<label class="tag-chip"><input type="checkbox" name="tags" value="{t_esc}" /><span>{t_esc}</span></label>'
        )

    report_cards = []
    if os.path.isdir(OUTPUT_DIR):
        files = sorted(
            [f for f in os.listdir(OUTPUT_DIR) if f.startswith("mirobody_proactive_report_") and f.endswith(".html")],
            reverse=True,
        )[:16]
        for fname in files:
            meta = _parse_report_card_meta(fname, users_by_id=users_by_id)
            f_q = urllib.parse.quote(fname)
            f_url = "/studio/report/" + f_q
            pdf_url = "/studio/export/pdf/" + f_q
            png_url = "/studio/export/png/" + f_q
            gc, gbg, gbd = _grade_badge_style(meta["grade"])
            grade_badge = (
                f'<span class="doc-grade" style="color:{gc};background:{gbg};border-color:{gbd};">{html.escape(meta["grade"])}</span>'
                if meta["grade"]
                else ""
            )
            meta_span = f'<span class="doc-person-meta">{html.escape(meta["person_meta"])}</span>' if meta["person_meta"] else ""
            checkup_line = (
                f'<div class="doc-checkup-date">体检：{html.escape(meta["checkup_text"])}</div>'
                if meta["checkup_text"]
                else ""
            )
            more_risk = (
                f'<span class="doc-risk-more">另 {meta["extra_risk_count"]} 项重点风险</span>'
                if meta["extra_risk_count"] > 0
                else ""
            )
            risk_block = (
                f'<div class="doc-risk"><div class="doc-risk-text">{html.escape(meta["top_risk"])}</div>{more_risk}</div>'
                if meta["top_risk"]
                else ""
            )
            stats_line = f'<div class="doc-stats">{html.escape(meta["stats_text"])}</div>' if meta["stats_text"] else ""
            ctx_pills = "".join(f'<span class="ctx-pill">{html.escape(t)}</span>' for t in meta["context_tags"])
            ctx_row = f'<div class="doc-ctx-tags">{ctx_pills}</div>' if ctx_pills else ""
            report_cards.append(f"""
            <div class="doc-file-card">
              <a class="doc-card-main" href="{f_url}" target="_blank">
                <div class="doc-head">
                  <div class="doc-person-wrap">
                    <span class="doc-person">{html.escape(meta["person_name"])}</span>
                    {meta_span}
                  </div>
                  {grade_badge}
                </div>
                <div class="doc-dates">
                  <div class="doc-issue-date">出具：{html.escape(meta["date_str"])} {html.escape(meta["time_str"])}</div>
                  {checkup_line}
                </div>
                {risk_block}
                {stats_line}
                {ctx_row}
              </a>
              <div class="doc-footer">
                <a class="act-btn" href="{f_url}" target="_blank">查看报告</a>
                <span class="doc-actions">
                  <a class="act-btn" href="{pdf_url}" title="下载适合手机直接阅读的窄幅 PDF">手机PDF</a>
                  <a class="act-btn" href="{png_url}" title="下载适合微信发送的高清手机长图">长图</a>
                  <form method="POST" action="/studio/delete" style="display:inline;margin:0;" onsubmit="return confirm('确定删除这份报告及其导出的 PDF/长图吗？');">
                    <input type="hidden" name="fname" value="{html.escape(fname)}" />
                    <button type="submit" class="act-btn act-del" title="删除此报告">删除</button>
                  </form>
                </span>
              </div>
            </div>""")

    history_html = (
        f'<div class="doc-grid">{"".join(report_cards)}</div>'
        if report_cards
        else '<p class="muted">暂无已生成的报告，点击上方按钮即可读取当前已解析指标生成第一份。</p>'
    )

    err_html = f'<div class="err-box">{html.escape(error_msg)}</div>' if error_msg else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>健康报告工作台</title>
<style>
  body {{ margin:0; background:#f6f4ef; color:#1f2933; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif; }}
  .wrap {{ max-width:860px; margin:24px auto 48px; padding:0 20px; }}
  .card {{ background:#fff; border:1px solid #e5e1d8; border-radius:18px; padding:24px; box-shadow:0 6px 20px rgba(0,0,0,0.03); margin-bottom:20px; }}
  .header-row {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; }}
  h1 {{ margin:0 0 6px; font-size:22px; color:#134e4a; display:flex; align-items:center; gap:8px; }}
  .sub {{ margin:0; font-size:13.5px; color:#5b6770; line-height:1.5; }}
  .refresh-link {{ font-size:13px; color:#134e4a; text-decoration:none; font-weight:600; padding:4px 10px; background:#e6f4f1; border-radius:6px; }}
  .refresh-link:hover {{ background:#134e4a; color:#fff; }}
  label.fld {{ display:block; font-size:13px; font-weight:700; margin:14px 0 6px; color:#374151; }}
  select, input[type=text], input[type=number] {{ width:100%; padding:10px 12px; border:1px solid #d1d5db; border-radius:10px; font-size:14px; box-sizing:border-box; background:#fff; }}
  .row-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
  @media (max-width: 560px) {{ .row-2 {{ grid-template-columns:1fr; }} }}
  .tags {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:6px; }}
  .tag-chip {{ display:inline-flex; align-items:center; gap:6px; background:#f3f4f6; padding:6px 12px; border-radius:999px; font-size:13px; cursor:pointer; }}
  .btn {{ margin-top:20px; width:100%; background:#134e4a; color:#fff; border:none; border-radius:12px; padding:13px; font-size:15px; font-weight:700; cursor:pointer; transition:opacity 0.15s; }}
  .btn:hover {{ opacity:0.93; }}
  .btn:disabled {{ opacity:0.6; cursor:wait; }}
  .err-box {{ background:#fef2f2; color:#991b1b; border:1px solid #fecaca; border-radius:10px; padding:10px 14px; font-size:13px; margin-bottom:14px; }}
  .sec-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; }}
  .sec-head h2 {{ margin:0; font-size:16px; color:#134e4a; }}
  .sec-count {{ font-size:12px; color:#6b7280; }}
  .doc-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(340px, 1fr)); gap:14px; }}
  .doc-file-card {{
    display:flex;
    flex-direction:column;
    text-decoration:none;
    color:inherit;
    background:#fcfbf8;
    border:1px solid #e5e1d8;
    border-radius:14px;
    padding:16px;
    position:relative;
    transition:transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
  }}
  .doc-file-card:hover {{
    transform:translateY(-2px);
    box-shadow:0 8px 20px rgba(19,78,74,0.08);
    border-color:#134e4a;
    background:#fff;
  }}
  .doc-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:10px; margin-bottom:10px; }}
  .doc-person-wrap {{ display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; }}
  .doc-person {{ font-size:16.5px; font-weight:700; color:#134e4a; line-height:1.3; }}
  .doc-person-meta {{ font-size:12.5px; color:#5b6770; font-weight:500; }}
  .doc-grade {{
    font-size:11.5px;
    font-weight:700;
    padding:3px 10px;
    border-radius:999px;
    border:1px solid transparent;
    white-space:nowrap;
    flex-shrink:0;
  }}
  .doc-dates {{ display:flex; flex-direction:column; gap:3px; font-size:12.5px; margin-bottom:10px; }}
  .doc-issue-date {{ color:#1f2933; font-weight:600; font-variant-numeric:tabular-nums; }}
  .doc-checkup-date {{ color:#6b7280; font-variant-numeric:tabular-nums; }}
  .doc-risk {{
    background:#f8f7f3;
    border:1px solid #ebe6dc;
    border-radius:10px;
    padding:9px 11px;
    margin-bottom:10px;
  }}
  .doc-risk-text {{
    font-size:12.5px;
    color:#374151;
    line-height:1.45;
    display:-webkit-box;
    -webkit-line-clamp:2;
    -webkit-box-orient:vertical;
    overflow:hidden;
  }}
  .doc-risk-more {{
    display:inline-block;
    margin-top:4px;
    font-size:11px;
    font-weight:600;
    color:#b45309;
  }}
  .doc-stats {{
    font-size:12px;
    color:#4b5563;
    font-variant-numeric:tabular-nums;
    margin-bottom:8px;
  }}
  .doc-ctx-tags {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px; }}
  .ctx-pill {{
    font-size:11px;
    font-weight:600;
    color:#134e4a;
    background:#e6f4f1;
    padding:2px 8px;
    border-radius:999px;
    white-space:nowrap;
  }}
  .doc-footer {{
    margin-top:auto;
    padding-top:10px;
    border-top:1px dashed #e5e1d8;
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:8px;
    font-size:12px;
  }}
  .doc-card-main {{ text-decoration:none; color:inherit; display:block; flex:1; }}
  .doc-actions {{ display:flex; gap:6px; flex-wrap:nowrap; }}
  .act-btn {{
    text-decoration:none;
    font-size:11px;
    font-weight:700;
    color:#134e4a;
    background:#e6f4f1;
    padding:4px 9px;
    border-radius:6px;
    border:none;
    cursor:pointer;
    font-family:inherit;
    line-height:1.4;
    white-space:nowrap;
  }}
  .act-btn:hover {{ background:#134e4a; color:#fff; }}
  .act-del {{ color:#b91c1c; background:#fef2f2; }}
  .act-del:hover {{ background:#b91c1c; color:#fff; }}
  .muted {{ color:#6b7280; font-size:13px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="header-row">
      <div>
        <h1>
          <span>AI 主动风险挖掘与食养报告</span>
        </h1>
        <p class="sub">读取 Mirobody 已解析的标准化体检指标，一键运行主动风险挖掘与深度食养方案。</p>
      </div>
      <a class="refresh-link" href="/studio/view" title="刷新指标与用户列表">刷新档案</a>
    </div>

    {err_html}
    <form method="POST" action="/studio/generate" onsubmit="const b=document.getElementById('go'); b.disabled=true; b.textContent='正在运行三层风险挖掘 + DeepSeek 深度推理（约 15~30 秒）...';">
      <label class="fld">选择 Mirobody 档案用户</label>
      <select id="user-select" name="user_id">{"".join(user_options)}</select>

      <label class="fld">报告显示代号（脱敏，不含真实姓名/身份证）</label>
      <input id="label-input" type="text" name="label" value="{html.escape(default_label)}" placeholder="如：家庭成员A / 2026年度档案" />

      <div class="row-2">
        <div>
          <label class="fld">性别（选填，用于校准男女阈值与食养禁忌）</label>
          <select id="gender-select" name="gender">
            <option value="">暂不指定</option>
            <option value="女">女</option>
            <option value="男">男</option>
          </select>
        </div>
        <div>
          <label class="fld">年龄（周岁，选填）</label>
          <input id="age-input" type="number" name="age" min="1" max="120" placeholder="如：35" />
        </div>
      </div>

      <label class="fld">可选：叠加近期主观体感标签（多选）</label>
      <div class="tags">{"".join(tag_checks)}</div>

      <label class="fld">可选：近期用药 / 调理一句话备注</label>
      <input type="text" name="recent_note" placeholder="如：近3个月在吃二甲双胍、晚间戒夜宵 / 备孕期 / 正在喝陈皮山楂茶" />

      <button id="go" class="btn" type="submit">一键生成主动风险与食养报告</button>
    </form>
  </div>

  <div class="card">
    <div class="sec-head">
      <h2>历史生成的健康报告</h2>
      <span class="sec-count">共 {len(report_cards)} 份</span>
    </div>
    {history_html}
  </div>
</div>
<script>
(function() {{
  var sel = document.getElementById('user-select');
  var labelEl = document.getElementById('label-input');
  var genderEl = document.getElementById('gender-select');
  var ageEl = document.getElementById('age-input');
  function syncUserProfile() {{
    if (!sel || !sel.options.length) return;
    var opt = sel.options[sel.selectedIndex];
    if (!opt) return;
    var name = opt.getAttribute('data-name') || '';
    var gender = opt.getAttribute('data-gender') || '';
    var age = opt.getAttribute('data-age') || '';
    if (labelEl && name) labelEl.value = name;
    if (genderEl) genderEl.value = gender;
    if (ageEl) ageEl.value = age;
  }}
  if (sel) {{
    sel.addEventListener('change', syncUserProfile);
  }}
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', syncUserProfile);
  }} else {{
    syncUserProfile();
  }}
}})();
</script>
</body>
</html>"""


class UnifiedGatewayHandler(BaseHTTPRequestHandler):
    def _is_studio_path(self):
        return self.path == "/studio" or self.path.startswith("/studio/")

    def do_GET(self):
        if self._is_studio_path():
            self._handle_studio_get()
            return
        self._proxy_request("GET")

    def do_POST(self):
        if self._is_studio_path():
            self._handle_studio_post()
            return
        self._proxy_request("POST")

    def do_PUT(self):
        self._proxy_request("PUT")

    def do_DELETE(self):
        self._proxy_request("DELETE")

    def do_PATCH(self):
        self._proxy_request("PATCH")

    def do_HEAD(self):
        if self._is_studio_path():
            self.send_response(200)
            self.end_headers()
            return
        self._proxy_request("HEAD")

    def do_OPTIONS(self):
        self._proxy_request("OPTIONS")

    def _handle_studio_get(self):
        p = self.path
        if p in ("/studio", "/studio/", "/studio/view"):
            body = _render_studio_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if p.startswith("/studio/report/"):
            fname = os.path.basename(urllib.parse.unquote(p[len("/studio/report/"):]))
            fpath = os.path.join(OUTPUT_DIR, fname)
            if os.path.isfile(fpath) and fname.endswith(".html"):
                with open(fpath, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

        if p.startswith("/studio/export/pdf/") or p.startswith("/studio/export/png/"):
            is_pdf = p.startswith("/studio/export/pdf/")
            prefix = "/studio/export/pdf/" if is_pdf else "/studio/export/png/"
            fname = os.path.basename(urllib.parse.unquote(p[len(prefix):]))
            html_path = os.path.join(OUTPUT_DIR, fname)
            if os.path.isfile(html_path) and fname.endswith(".html"):
                try:
                    out_path = export_mobile_pdf(html_path) if is_pdf else export_mobile_png(html_path)
                    with open(out_path, "rb") as f:
                        data = f.read()
                    mime = "application/pdf" if is_pdf else "image/png"
                    dl_name = os.path.basename(out_path)
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Disposition", f'attachment; filename="{dl_name}"')
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception as e:
                    self.send_error(500, f"Export failed: {e}")
                    return

        self.send_error(404, "Not Found")

    def _handle_studio_post(self):
        p = self.path
        if p == "/studio/delete":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            form = urllib.parse.parse_qs(raw)
            fname = os.path.basename((form.get("fname") or [""])[0].strip())
            if fname.startswith("mirobody_proactive_report_") and fname.endswith(".html"):
                base = fname[:-5]
                for suffix in (".html", ".json", "_mobile.pdf", "_mobile.png"):
                    fpath = os.path.join(OUTPUT_DIR, base + suffix)
                    if os.path.isfile(fpath):
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
            self.send_response(303)
            self.send_header("Location", "/studio/view")
            self.end_headers()
            return

        if p == "/studio/generate":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            form = urllib.parse.parse_qs(raw)
            user_id = (form.get("user_id") or ["1"])[0].strip() or "1"
            label = (form.get("label") or ["家庭主档案"])[0].strip() or "家庭主档案"
            gender = (form.get("gender") or [""])[0].strip()
            if gender not in ("男", "女"):
                gender = ""
            raw_age = (form.get("age") or [""])[0].strip()
            age = None
            if raw_age.isdigit():
                val = int(raw_age)
                if 1 <= val <= 120:
                    age = val
            recent_note = (form.get("recent_note") or [""])[0].strip()[:200]
            tags = form.get("tags") or []

            try:
                html_path, _, _, _ = run_pipeline(
                    user_id=user_id,
                    label=label,
                    constitution_tags=tags,
                    gender=gender,
                    age=age,
                    recent_note=recent_note,
                )
                fname = os.path.basename(html_path)
                self.send_response(303)
                self.send_header("Location", f"/studio/report/{urllib.parse.quote(fname)}")
                self.end_headers()
            except Exception as e:
                body = _render_studio_html(error_msg=f"生成失败：{e}").encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            return

        self.send_error(404, "Not Found")

    def _proxy_websocket(self):
        self.close_connection = True
        try:
            backend_sock = socket.create_connection((BACKEND_HOST, BACKEND_PORT), timeout=15)
        except OSError as e:
            self.send_error(502, f"Bad Gateway (WebSocket backend unreachable: {e})")
            return

        try:
            req_lines = [f"{self.command} {self.path} HTTP/1.1\r\n"]
            for k, v in self.headers.items():
                if k.lower() == "host":
                    continue
                req_lines.append(f"{k}: {v}\r\n")
            req_lines.append(f"Host: localhost:{BACKEND_PORT}\r\n\r\n")
            backend_sock.sendall("".join(req_lines).encode("latin-1"))

            first_chunk = backend_sock.recv(65536)
            if not first_chunk:
                self.send_error(502, "Bad Gateway (Empty WebSocket handshake response)")
                return

            status_line = first_chunk.split(b"\r\n", 1)[0].decode("latin-1", errors="replace")
            path_only = self.path.split("?", 1)[0]
            print(f'[Gateway] {self.address_string()} - "WS {path_only}" {status_line}', flush=True)

            client_sock = self.connection
            client_sock.sendall(first_chunk)

            for sock in (client_sock, backend_sock):
                try:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except OSError:
                    pass
                sock.settimeout(None)

            sockets = [client_sock, backend_sock]
            half_closed = False
            while sockets:
                timeout = 2.0 if half_closed else 60.0
                readable, _, exceptional = select.select(sockets, [], sockets, timeout)
                if exceptional:
                    break
                if not readable:
                    if half_closed:
                        break
                    continue
                for src in readable:
                    if src not in sockets:
                        continue
                    dst = backend_sock if src is client_sock else client_sock
                    try:
                        data = src.recv(65536)
                    except OSError:
                        data = b""
                    if not data:
                        sockets = [s for s in sockets if s is not src]
                        half_closed = True
                        try:
                            dst.shutdown(socket.SHUT_WR)
                        except OSError:
                            pass
                        continue
                    try:
                        dst.sendall(data)
                    except OSError:
                        sockets = []
                        break
        except OSError:
            pass
        finally:
            try:
                backend_sock.close()
            except OSError:
                pass

    def _proxy_request(self, method):
        import gzip

        if "websocket" in self.headers.get("Upgrade", "").lower():
            self._proxy_websocket()
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length > 0 else None

        headers = {}
        for k, v in self.headers.items():
            k_lower = k.lower()
            if k_lower in ("connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade", "accept-encoding"):
                continue
            headers[k] = v

        headers["Host"] = f"localhost:{BACKEND_PORT}"
        # Request uncompressed identity to make HTML injection direct
        headers["Accept-Encoding"] = "identity"

        # Bypass 304 conditional request headers for HTML pages to ensure fresh injection
        is_html_route = (
            self.path == "/"
            or self.path.startswith("/data")
            or self.path.startswith("/indicators")
            or self.path.startswith("/chat")
        )
        if is_html_route:
            for h in ("If-None-Match", "if-none-match", "If-Modified-Since", "if-modified-since"):
                headers.pop(h, None)

        try:
            conn = http.client.HTTPConnection(BACKEND_HOST, BACKEND_PORT, timeout=300)
            conn.request(method, self.path, body=body, headers=headers)
            res = conn.getresponse()

            content_type = res.getheader("Content-Type", "")
            if "text/event-stream" in content_type.lower():
                self.close_connection = True
                self.send_response(res.status, res.reason)
                for k, v in res.getheaders():
                    if k.lower() in (
                        "transfer-encoding",
                        "content-length",
                        "connection",
                        "content-encoding",
                        "cache-control",
                        "x-accel-buffering",
                    ):
                        continue
                    self.send_header(k, v)
                self.send_header("Connection", "close")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()
                if method != "HEAD":
                    if conn.sock is not None:
                        conn.sock.settimeout(None)
                    try:
                        while True:
                            chunk = res.read1(4096)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError, http.client.IncompleteRead):
                        pass
                conn.close()
                return

            res_body = res.read()

            content_encoding = res.getheader("Content-Encoding", "").lower()
            if "gzip" in content_encoding:
                try:
                    res_body = gzip.decompress(res_body)
                    content_encoding = ""
                except Exception:
                    pass

            # Inject our sidebar integration script into any HTML response
            injected = False
            if ("text/html" in content_type or b"<div id=\"root\">" in res_body or b"<!DOCTYPE html>" in res_body):
                if b"</body>" in res_body:
                    res_body = res_body.replace(b"</body>", INJECT_JS.encode("utf-8") + b"</body>", 1)
                    injected = True
                elif b"</html>" in res_body:
                    res_body = res_body.replace(b"</html>", INJECT_JS.encode("utf-8") + b"</html>", 1)
                    injected = True
                else:
                    res_body = res_body + INJECT_JS.encode("utf-8")
                    injected = True

            self.send_response(res.status, res.reason)
            for k, v in res.getheaders():
                k_lower = k.lower()
                if k_lower in ("transfer-encoding", "content-length", "connection", "content-encoding"):
                    continue
                if injected and k_lower in ("etag", "cache-control"):
                    continue
                self.send_header(k, v)

            if injected:
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")

            self.send_header("Content-Length", str(len(res_body)))
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(res_body)
            conn.close()

        except Exception as e:
            self.send_error(502, f"Bad Gateway (Mirobody backend {BACKEND_HOST}:{BACKEND_PORT} unreachable: {e})")

    def log_message(self, fmt, *args):
        if "/assets/" not in str(args):
            print(f"[Gateway] {self.address_string()} - {fmt % args}", flush=True)


class GatewayHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    server = GatewayHTTPServer((HOST, PORT), UnifiedGatewayHandler)
    print("=" * 68, flush=True)
    print("🚀 Mirobody 统一健康中枢 & 报告工作台已就绪！", flush=True)
    print(f"👉 统一访问入口: http://{HOST}:{PORT}", flush=True)
    print(f"👉 Mirobody 底座端口: http://{BACKEND_HOST}:{BACKEND_PORT}", flush=True)
    print("=" * 68, flush=True)
    server.serve_forever()
