#!/usr/bin/env python3
"""Lightweight Local Web Studio for One-Click Proactive Health Risk & Food-Therapy Reports.

Zero external dependencies (Python standard library only).
Runs on http://127.0.0.1:18065 alongside Mirobody (http://127.0.0.1:18060).
"""

import html
import json
import os
import re
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from generate_from_mirobody import run_pipeline
from src.exporter import export_mobile_pdf, export_mobile_png
from src.mirobody_reader import list_users_with_uploads

HOST = os.environ.get("STUDIO_BIND", "127.0.0.1")
PORT = int(os.environ.get("STUDIO_PORT", "18065"))
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


def _parse_report_card_meta(fname):
    """Extract readable date, time, title, grade, and stats for a generated report file."""
    base = fname[:-5]  # strip .html
    # Parse timestamp from mirobody_proactive_report_u1_20261121_104933
    m = re.search(r"_u([^_]+)_(\d{8})_(\d{6})$", base)
    user_tag = f"用户 #{m.group(1)}" if m else "健康档案"
    if m:
        dt = datetime.strptime(m.group(2) + m.group(3), "%Y%m%d%H%M%S")
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H:%M")
    else:
        mtime = os.path.getmtime(os.path.join(OUTPUT_DIR, fname))
        dt = datetime.fromtimestamp(mtime)
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H:%M")

    title = "深度体检风险洞察与食养方案"
    grade = ""
    stats_text = ""

    json_path = os.path.join(OUTPUT_DIR, base + ".json")
    if os.path.isfile(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            rep = data.get("report") or {}
            ms = data.get("mined_summary") or {}
            if rep.get("report_title"):
                title = rep["report_title"]
            if rep.get("overall_grade"):
                grade = rep["overall_grade"]
            if ms.get("total_observations"):
                stats_text = f"{ms['total_observations']} 项 · 🔴 {ms.get('red_count', 0)} · 🟡 {ms.get('yellow_count', 0)}"
        except Exception:
            pass

    return {
        "fname": fname,
        "user_tag": user_tag,
        "date_str": date_str,
        "time_str": time_str,
        "title": title,
        "grade": grade,
        "stats_text": stats_text,
    }


def _render_home(error_msg=""):
    try:
        users = list_users_with_uploads()
    except Exception as e:
        users = []
        error_msg = error_msg or f"连接 Mirobody 数据库失败：{e}"

    user_options = []
    for u in users:
        uid = str(u["user_id"])
        txt = f"用户 #{uid} — {u['obs_count']} 项指标 / {u['file_count']} 份原件 ({u['first_date']} ~ {u['last_date']})"
        user_options.append(f'<option value="{html.escape(uid)}">{html.escape(txt)}</option>')
    if not user_options:
        user_options.append('<option value="1">用户 #1（请先在 Mirobody 上传体检报告）</option>')

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
        )[:12]
        for fname in files:
            meta = _parse_report_card_meta(fname)
            f_q = urllib.parse.quote(fname)
            f_url = "/report/" + f_q
            pdf_url = "/export/pdf/" + f_q
            png_url = "/export/png/" + f_q
            grade_badge = f'<span class="doc-grade">{html.escape(meta["grade"])}</span>' if meta["grade"] else ""
            stats_line = f'<div class="doc-stats">{html.escape(meta["stats_text"])}</div>' if meta["stats_text"] else ""
            report_cards.append(f"""
            <div class="doc-file-card">
              <a class="doc-card-main" href="{f_url}" target="_blank">
                <div class="doc-icon-row">
                  <div class="doc-icon" aria-hidden="true">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                      <line x1="8" y1="13" x2="16" y2="13"/>
                      <line x1="8" y1="17" x2="13" y2="17"/>
                    </svg>
                  </div>
                  {grade_badge}
                </div>
                <div class="doc-title">{html.escape(meta["title"])}</div>
                {stats_line}
              </a>
              <div class="doc-footer">
                <span class="doc-date">{html.escape(meta["date_str"])} {html.escape(meta["time_str"])}</span>
                <span class="doc-actions">
                  <a class="act-btn" href="{pdf_url}" title="下载适合手机直接阅读的窄幅 PDF">手机PDF</a>
                  <a class="act-btn" href="{png_url}" title="下载适合微信发送的高清手机长图">长图</a>
                  <form method="POST" action="/delete" style="display:inline;margin:0;" onsubmit="return confirm('确定删除这份报告及其导出的 PDF/长图吗？');">
                    <input type="hidden" name="fname" value="{html.escape(fname)}" />
                    <button type="submit" class="act-btn act-del" title="删除此报告">删除</button>
                  </form>
                </span>
              </div>
            </div>""")

    history_html = (
        f'<div class="doc-grid">{"".join(report_cards)}</div>'
        if report_cards
        else '<p class="muted">暂无已生成的报告，点击上方按钮即可生成第一份。</p>'
    )

    err_html = f'<div class="err-box">{html.escape(error_msg)}</div>' if error_msg else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Mirobody × AI 主动风险挖掘与食养报告工作台</title>
<style>
  body {{ margin:0; background:#f6f4ef; color:#1f2933; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif; }}
  .wrap {{ max-width:820px; margin:32px auto 56px; padding:0 16px; }}
  .card {{ background:#fff; border:1px solid #e5e1d8; border-radius:18px; padding:26px; box-shadow:0 8px 24px rgba(0,0,0,0.04); margin-bottom:20px; }}
  h1 {{ margin:0 0 6px; font-size:22px; color:#134e4a; }}
  .sub {{ margin:0 0 20px; font-size:13.5px; color:#5b6770; }}
  .sub a {{ color:#134e4a; font-weight:600; }}
  label.fld {{ display:block; font-size:13px; font-weight:700; margin:14px 0 6px; color:#374151; }}
  select, input[type=text], input[type=number] {{ width:100%; padding:10px 12px; border:1px solid #d1d5db; border-radius:10px; font-size:14px; box-sizing:border-box; background:#fff; }}
  .row-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
  @media (max-width: 560px) {{ .row-2 {{ grid-template-columns:1fr; }} }}
  .tags {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:6px; }}
  .tag-chip {{ display:inline-flex; align-items:center; gap:6px; background:#f3f4f6; padding:6px 12px; border-radius:999px; font-size:13px; cursor:pointer; }}
  .btn {{ margin-top:22px; width:100%; background:#134e4a; color:#fff; border:none; border-radius:12px; padding:13px; font-size:15px; font-weight:700; cursor:pointer; }}
  .btn:hover {{ opacity:0.93; }}
  .btn:disabled {{ opacity:0.6; cursor:wait; }}
  .err-box {{ background:#fef2f2; color:#991b1b; border:1px solid #fecaca; border-radius:10px; padding:10px 14px; font-size:13px; margin-bottom:14px; }}
  .sec-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; }}
  .sec-head h2 {{ margin:0; font-size:16px; color:#134e4a; }}
  .sec-count {{ font-size:12px; color:#6b7280; }}
  .doc-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(225px, 1fr)); gap:14px; }}
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
    box-shadow:0 10px 22px rgba(19,78,74,0.10);
    border-color:#134e4a;
    background:#fff;
  }}
  .doc-icon-row {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }}
  .doc-icon {{
    width:40px;
    height:40px;
    border-radius:10px;
    background:#e6f4f1;
    color:#134e4a;
    display:flex;
    align-items:center;
    justify-content:center;
  }}
  .doc-grade {{
    font-size:11px;
    font-weight:700;
    padding:3px 9px;
    border-radius:999px;
    background:#fffbeb;
    color:#b45309;
    border:1px solid #fde68a;
  }}
  .doc-title {{
    font-size:14.5px;
    font-weight:700;
    color:#1f2933;
    line-height:1.4;
    margin-bottom:6px;
  }}
  .doc-stats {{
    font-size:12px;
    color:#5b6770;
    margin-bottom:12px;
  }}
  .doc-footer {{
    margin-top:auto;
    padding-top:10px;
    border-top:1px dashed #e5e1d8;
    display:flex;
    justify-content:space-between;
    align-items:center;
    font-size:12px;
  }}
  .doc-card-main {{ text-decoration:none; color:inherit; display:block; flex:1; }}
  .doc-date {{ color:#6b7280; font-variant-numeric:tabular-nums; font-size:11.5px; }}
  .doc-actions {{ display:flex; gap:6px; }}
  .act-btn {{
    text-decoration:none;
    font-size:11px;
    font-weight:700;
    color:#134e4a;
    background:#e6f4f1;
    padding:3px 8px;
    border-radius:6px;
    border:none;
    cursor:pointer;
    font-family:inherit;
    line-height:1.4;
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
    <h1>AI 主动健康风险挖掘与食养报告工作台</h1>
    <p class="sub">Step 1：在 <a href="http://localhost:18060" target="_blank">Mirobody 底座 (localhost:18060)</a> 上传体检 PDF/照片 → Step 2：在这里一键生成专业报告。</p>
    {err_html}
    <form method="POST" action="/generate" onsubmit="const b=document.getElementById('go'); b.disabled=true; b.textContent='正在运行三层风险挖掘 + DeepSeek-Flash 深度推理（约 15~30 秒）...';">
      <label class="fld">选择 Mirobody 档案用户</label>
      <select name="user_id">{"".join(user_options)}</select>

      <label class="fld">报告显示代号（脱敏，不含真实姓名/身份证）</label>
      <input type="text" name="label" value="家庭主档案" placeholder="如：家庭主档案 / VIP客户-张女士" />

      <div class="row-2">
        <div>
          <label class="fld">性别（选填，用于校准男女阈值与食养禁忌）</label>
          <select name="gender">
            <option value="">暂不指定</option>
            <option value="女">女</option>
            <option value="男">男</option>
          </select>
        </div>
        <div>
          <label class="fld">年龄（周岁，选填）</label>
          <input type="number" name="age" min="1" max="120" placeholder="如：35" />
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
      <h2>最近生成的报告</h2>
      <span class="sec-count">共 {len(report_cards)} 份档案</span>
    </div>
    {history_html}
  </div>
</div>
</body>
</html>"""


class StudioHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            body = _render_home().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path.startswith("/report/"):
            fname = os.path.basename(urllib.parse.unquote(self.path[len("/report/"):]))
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

        if self.path.startswith("/export/pdf/") or self.path.startswith("/export/png/"):
            is_pdf = self.path.startswith("/export/pdf/")
            prefix = "/export/pdf/" if is_pdf else "/export/png/"
            fname = os.path.basename(urllib.parse.unquote(self.path[len(prefix):]))
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

    def do_POST(self):
        if self.path == "/delete":
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
            self.send_header("Location", "/")
            self.end_headers()
            return

        if self.path != "/generate":
            self.send_error(404, "Not Found")
            return

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
            self.send_header("Location", f"/report/{urllib.parse.quote(fname)}")
            self.end_headers()
        except Exception as e:
            body = _render_home(error_msg=f"生成失败：{e}").encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[Studio] {self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), StudioHandler)
    print(f"[*] AI 主动健康风险与食养报告工作台已启动: http://{HOST}:{PORT}")
    server.serve_forever()
