"""体检报告解析层：支持 PDF（文本层/扫描页）与化验单照片 -> DeepSeek 多模态结构化提取。"""

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .deepseek_client import DeepSeekClient, extract_json_block
from .deid import deidentify_text

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

DATE_FILENAME_RE = re.compile(r"(20\d{2})[.\-_年](\d{1,2})[.\-_月](\d{1,2})")


def _infer_date_from_filename(filename: str) -> Optional[str]:
    m = DATE_FILENAME_RE.search(filename)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if 1 <= mo <= 12 and 1 <= d <= 31:
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def _normalize_date(raw_date: Any, filename: str) -> str:
    s = str(raw_date or "").strip()
    if re.match(r"^20\d{2}-\d{2}-\d{2}$", s):
        return s
    m = DATE_FILENAME_RE.search(s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    fallback = _infer_date_from_filename(filename)
    return fallback or "unknown"


EXTRACTION_PROMPT = """你是一位严谨的医学体检数据结构化助手。请从提供的体检报告/化验单内容中，提取核心检验指标与影像结论，并严格按以下 JSON 格式输出（不要输出多余解释）：

{
  "report_date": "YYYY-MM-DD（若只有年月则填 YYYY-MM-01，实在未知填 unknown）",
  "gender": "男 或 女 或 未知",
  "age": 35,
  "indicators": [
    {
      "code": "标准简写（优先严格使用以下统一代码: TG(甘油三酯), LDL-C(低密度脂蛋白胆固醇), HDL-C(高密度脂蛋白胆固醇), TC(总胆固醇), UA(尿酸), FBG(空腹血糖/葡萄糖), HbA1c(糖化血红蛋白), ALT(丙氨酸氨基转移酶), AST(天门冬氨酸氨基转移酶), GGT(γ-谷氨酰基转移酶), Cr(肌酐), eGFR(肾小球滤过率), VitD(25-羟基维生素D), TSH(促甲状腺激素), CRP(C反应蛋白), ESR(血沉), Ca(血钙), UACR(尿微量白蛋白/肌酐比值) 等）",
      "name": "中文指标名",
      "value": 1.88,
      "unit": "单位，如 mmol/L、μmol/L、U/L、ng/mL、%",
      "ref_low": 0.4,
      "ref_high": 1.7,
      "page": "P1"
    }
  ],
  "findings": [
    {
      "section": "如 腹部超声 / 甲状腺超声 / 颈动脉超声 / 胸部CT / 心电图 / 尿常规",
      "summary": "简明扼要的阳性/关注结论（如 轻度脂肪肝、甲状腺右叶小结节 3mm、颈动脉内膜增厚等；若全部正常也可简写为 未见明显异常）",
      "page": "P1"
    }
  ]
}

注意：
1. 务必核准小数点与单位，value 必须是纯数字（不要带箭头或单位），不要编造原文中没有的数值。
2. 若参考区间是 "<3.4" 这种单边上限，ref_low 填 null、ref_high 填 3.4；若为 ">1.0"，ref_low 填 1.0、ref_high 填 null。
3. 严禁输出真实姓名、身份证号、手机号、住院号、就诊卡号等个人隐私信息。
4. 重点提取：血脂四项（TG/LDL-C/HDL-C/TC）、血尿酸（UA）、空腹血糖（FBG）/糖化（HbA1c）、肝功（ALT/AST/GGT）、肾功（Cr/eGFR）、维生素D（VitD）、甲功（TSH）、血钙（Ca）及所有超声/CT/心电图阳性结论。
"""


def _extract_from_pdf_via_sips(pdf_path: Path, client: DeepSeekClient) -> Dict[str, Any]:
    """macOS 零依赖兜底：用系统自带 sips 将单页检验 PDF 转为高清 PNG 后走 deepseek-flash 视觉读图。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = Path(tmpdir) / "page_1.png"
        proc = subprocess.run(
            ["sips", "-s", "format", "png", str(pdf_path), "--out", str(img_path)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not img_path.exists():
            raise RuntimeError(f"无法使用 macOS sips 转换 PDF ({pdf_path.name}): {proc.stderr.strip()}")
        raw_resp = client.vision_extract(img_path, prompt=f"{EXTRACTION_PROMPT}\n\n文件名为：{pdf_path.name}")
        parsed = extract_json_block(raw_resp)
        for ind in parsed.get("indicators", []):
            ind.setdefault("page", "P1")
        for f in parsed.get("findings", []):
            f.setdefault("page", "P1")
        return {
            "report_date": _normalize_date(parsed.get("report_date"), pdf_path.name),
            "source_file": pdf_path.name,
            "gender": parsed.get("gender", "未知"),
            "age": parsed.get("age"),
            "indicators": parsed.get("indicators", []),
            "findings": parsed.get("findings", []),
        }


def _extract_from_pdf(pdf_path: Path, client: DeepSeekClient) -> Dict[str, Any]:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return _extract_from_pdf_via_sips(pdf_path, client)

    doc = fitz.open(str(pdf_path))
    text_chunks: List[str] = []
    scanned_pages: List[int] = []

    for idx, page in enumerate(doc):
        page_no = idx + 1
        txt = page.get_text("text").strip()
        if len(txt) >= 60:
            clean_txt = deidentify_text(txt)
            text_chunks.append(f"--- [P{page_no}] ---\n{clean_txt}")
        else:
            scanned_pages.append(idx)

    merged_indicators: List[Dict[str, Any]] = []
    merged_findings: List[Dict[str, Any]] = []
    report_meta: Dict[str, Any] = {"report_date": "unknown", "gender": "未知", "age": None}

    # 1. 优先用文本层一次抽取（成本极低、精度高）
    if text_chunks:
        full_text = "\n\n".join(text_chunks)
        # 若体检报告极长，按 18000 字分段避免超上下文
        chunk_size = 18000
        for start in range(0, len(full_text), chunk_size):
            piece = full_text[start : start + chunk_size]
            raw_resp = client.chat(
                messages=[
                    {"role": "system", "content": "你是严谨的体检数据结构化提取引擎，仅输出合法 JSON。"},
                    {"role": "user", "content": f"{EXTRACTION_PROMPT}\n\n以下是脱敏后的体检报告文本：\n{piece}"},
                ],
                model=client.text_model,
                temperature=0.1,
            )
            parsed = extract_json_block(raw_resp)
            if report_meta["report_date"] == "unknown" and parsed.get("report_date"):
                report_meta["report_date"] = parsed["report_date"]
            if report_meta["gender"] == "未知" and parsed.get("gender"):
                report_meta["gender"] = parsed["gender"]
            if report_meta["age"] is None and parsed.get("age"):
                report_meta["age"] = parsed["age"]
            merged_indicators.extend(parsed.get("indicators", []))
            merged_findings.extend(parsed.get("findings", []))

    # 2. 对纯图片扫描页，渲染成 PNG 走 deepseek-flash 原生视觉读图
    if scanned_pages:
        with tempfile.TemporaryDirectory() as tmpdir:
            for idx in scanned_pages[:15]:  # Demo 保护上限：单份扫描件最多 15 页
                page = doc[idx]
                pix = page.get_pixmap(dpi=160)
                img_path = Path(tmpdir) / f"page_{idx + 1}.png"
                pix.save(str(img_path))
                raw_resp = client.vision_extract(
                    img_path,
                    prompt=f"{EXTRACTION_PROMPT}\n\n当前页码为 P{idx + 1}。",
                )
                parsed = extract_json_block(raw_resp)
                if report_meta["report_date"] == "unknown" and parsed.get("report_date"):
                    report_meta["report_date"] = parsed["report_date"]
                if report_meta["gender"] == "未知" and parsed.get("gender"):
                    report_meta["gender"] = parsed["gender"]
                if report_meta["age"] is None and parsed.get("age"):
                    report_meta["age"] = parsed["age"]
                for ind in parsed.get("indicators", []):
                    ind.setdefault("page", f"P{idx + 1}")
                    merged_indicators.append(ind)
                for f in parsed.get("findings", []):
                    f.setdefault("page", f"P{idx + 1}")
                    merged_findings.append(f)

    doc.close()

    # 按 code 去重（保留后提取或首个完整项）
    dedup_ind: Dict[str, Dict[str, Any]] = {}
    for ind in merged_indicators:
        key = str(ind.get("code") or ind.get("name", "")).strip()
        if key and key not in dedup_ind:
            dedup_ind[key] = ind

    return {
        "report_date": _normalize_date(report_meta["report_date"], pdf_path.name),
        "source_file": pdf_path.name,
        "gender": report_meta["gender"],
        "age": report_meta["age"],
        "indicators": list(dedup_ind.values()),
        "findings": merged_findings,
    }


def _extract_from_image(img_path: Path, client: DeepSeekClient) -> Dict[str, Any]:
    raw_resp = client.vision_extract(img_path, prompt=f"{EXTRACTION_PROMPT}\n\n文件名为：{img_path.name}")
    parsed = extract_json_block(raw_resp)
    return {
        "report_date": _normalize_date(parsed.get("report_date"), img_path.name),
        "source_file": img_path.name,
        "gender": parsed.get("gender", "未知"),
        "age": parsed.get("age"),
        "indicators": parsed.get("indicators", []),
        "findings": parsed.get("findings", []),
    }


def _cache_file_for(path: Path, cache_dir: Path) -> Path:
    stat = path.stat()
    sig = f"{path.name}|{stat.st_size}|{int(stat.st_mtime)}"
    digest = hashlib.md5(sig.encode("utf-8")).hexdigest()[:12]
    safe_stem = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff._-]", "_", path.stem)[:40]
    return cache_dir / f"{safe_stem}_{digest}.json"


def extract_reports(
    input_paths: List[Path],
    client: DeepSeekClient,
    cache_dir: Optional[Path] = None,
    refresh_cache: bool = False,
) -> Dict[str, Any]:
    """批量解析多个体检文件（支持 PDF / 图片 / 已结构化 JSON），支持本地缓存避免重复调用 API。"""
    reports: List[Dict[str, Any]] = []
    profile: Dict[str, Any] = {"alias": "受检者A", "gender": "未知", "age": "未知"}
    constitution_selected: List[str] = []

    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)

    for path in input_paths:
        suffix = path.suffix.lower()
        if suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if "reports" in data:
                reports.extend(data["reports"])
                if "profile" in data:
                    profile.update(data["profile"])
                if "constitution_selected" in data:
                    constitution_selected = data["constitution_selected"]
            else:
                reports.append(data)
            continue

        if suffix not in IMAGE_EXTS and suffix != ".pdf":
            continue

        cache_path = _cache_file_for(path, cache_dir) if cache_dir else None
        rep: Optional[Dict[str, Any]] = None

        if cache_path and cache_path.exists() and not refresh_cache:
            print(f"[命中缓存] {path.name}")
            rep = json.loads(cache_path.read_text(encoding="utf-8"))
        elif suffix == ".pdf":
            print(f"[解析 PDF] {path.name} ...")
            rep = _extract_from_pdf(path, client)
        elif suffix in IMAGE_EXTS:
            print(f"[视觉读图] {path.name} ...")
            rep = _extract_from_image(path, client)

        if rep is not None:
            if cache_path and (refresh_cache or not cache_path.exists()):
                cache_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
            if rep.get("gender") not in (None, "", "未知"):
                profile["gender"] = rep["gender"]
            if rep.get("age") not in (None, "", "未知"):
                profile["age"] = rep["age"]
            reports.append(rep)

    return {
        "profile": profile,
        "constitution_selected": constitution_selected,
        "reports": reports,
    }
