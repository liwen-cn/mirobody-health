"""Zero-dependency Mobile HD Long-PNG & Mobile-Sized PDF Exporter using local Google Chrome."""

import os
import re
import shutil
import subprocess
import tempfile


CHROME_CANDIDATES = [
    os.environ.get("CHROME_BIN", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]


def find_chrome():
    for path in CHROME_CANDIDATES:
        if path and os.path.isfile(path):
            return path
    raise RuntimeError("未找到 Google Chrome / Chromium，无法导出手机长图或手机版 PDF。")


MAX_BITMAP_HEIGHT = 32000


def _prepare_mobile_html(html_path, for_pdf=False, width=430):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    if for_pdf:
        page_css = (
            ".page { width: 100% !important; max-width: __WIDTH__px !important; "
            "margin: 0 auto !important; padding: 10px 8px 24px !important; }"
        )
    else:
        # Headless Chrome on macOS uses a 500px minimum layout viewport; pinning margin: 0
        # with an exact width keeps .page aligned to x=0 so the right edge is never clipped.
        page_css = (
            ".page { width: __WIDTH__px !important; max-width: __WIDTH__px !important; "
            "margin: 0 !important; padding: 14px 12px 32px !important; }"
        )
    page_css = page_css.replace("__WIDTH__", str(width))

    # Inject clean mobile export overrides: hide toolbar, enforce comfortable mobile typography
    extra_css = (
        """
    <style>
      .toolbar { display: none !important; }
      body { background: #f6f4ef !important; overflow-x: hidden !important; }
      """
        + page_css
        + """
      .stats-strip { grid-template-columns: repeat(2, 1fr) !important; }
      .exec-metrics, .pain-grid, .ft-body { grid-template-columns: 1fr !important; }
      .rc-item { flex-direction: column !important; gap: 4px !important; }
      .hero { padding: 22px 18px 18px !important; }
      .hero h1 { font-size: 21px !important; }
      .ind-pill, .em-chip, .pain-block, .exec-sec, .prot-val { overflow-wrap: anywhere; word-break: break-word; }
    """
    )
    if for_pdf:
        # 114mm width (~430px) = native phone reading width so users NEVER need to zoom in WeChat!
        extra_css += """
      @page { size: 114mm 210mm; margin: 4mm; }
      body { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
      .pain-card, .ft-card, .doc-card, .prot-card, .sys-summary-card, .exec-card { break-inside: avoid; }
    """
    extra_css += "</style>"

    measure_script = """
    <script>
      window.addEventListener('load', function() {
        var p = document.querySelector('.page');
        var h = Math.ceil(Math.max(p ? p.getBoundingClientRect().bottom : 0, document.documentElement.scrollHeight));
        document.title = 'EXPORT_HEIGHT:' + h;
      });
    </script>
    """
    patched = content.replace("</head>", extra_css + measure_script + "\n</head>", 1)
    tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
    tmp.write(patched)
    tmp.close()
    return tmp.name


def export_mobile_png(html_path, png_path=None, width=430, scale=2):
    """Export an HTML report as a crisp Retina mobile long PNG (430px @2x = 860px wide)."""
    chrome = find_chrome()
    html_abs = os.path.abspath(html_path)
    if not png_path:
        png_path = os.path.splitext(html_abs)[0] + "_mobile.png"
    png_abs = os.path.abspath(png_path)

    tmp_html = _prepare_mobile_html(html_abs, for_pdf=False, width=width)
    try:
        file_url = "file://" + tmp_html
        # Step 1: measure exact mobile scrollHeight
        probe = subprocess.run(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                f"--window-size={width},900",
                "--virtual-time-budget=2000",
                "--dump-dom",
                file_url,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        m = re.search(r"EXPORT_HEIGHT:(\d+)", probe.stdout)
        height = int(m.group(1)) + 24 if m else 3200
        height = max(height, 900)
        eff_scale = scale
        if height * eff_scale > MAX_BITMAP_HEIGHT and eff_scale > 1:
            eff_scale = 1
        height = min(height, MAX_BITMAP_HEIGHT // eff_scale)

        # Step 2: render exact-height Retina PNG
        subprocess.run(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                f"--window-size={width},{height}",
                f"--force-device-scale-factor={eff_scale}",
                "--hide-scrollbars",
                "--virtual-time-budget=2000",
                f"--screenshot={png_abs}",
                file_url,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return png_abs
    finally:
        if os.path.exists(tmp_html):
            os.remove(tmp_html)


def export_mobile_pdf(html_path, pdf_path=None):
    """Export an HTML report as a mobile-width PDF (114mm wide — full-size readable on phones without zooming)."""
    chrome = find_chrome()
    html_abs = os.path.abspath(html_path)
    if not pdf_path:
        pdf_path = os.path.splitext(html_abs)[0] + "_mobile.pdf"
    pdf_abs = os.path.abspath(pdf_path)

    tmp_html = _prepare_mobile_html(html_abs, for_pdf=True)
    try:
        file_url = "file://" + tmp_html
        subprocess.run(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--no-pdf-header-footer",
                "--virtual-time-budget=2000",
                f"--print-to-pdf={pdf_abs}",
                file_url,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return pdf_abs
    finally:
        if os.path.exists(tmp_html):
            os.remove(tmp_html)
