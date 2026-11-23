"""单一 DeepSeek API 网关客户端（零外部依赖，兼容 OpenAI 协议）。"""

import base64
import json
import mimetypes
import os
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


def _build_ssl_context() -> ssl.SSLContext:
    """构造 SSL 上下文，兼容 macOS 系统自带 Python 3.9 缺少默认 CA 证书束的情况。"""
    ca_candidates = [
        "/etc/ssl/cert.pem",
        "/opt/homebrew/etc/openssl@3/cert.pem",
        "/usr/local/etc/openssl@3/cert.pem",
    ]
    for ca in ca_candidates:
        if os.path.exists(ca):
            return ssl.create_default_context(cafile=ca)
    return ssl.create_default_context()


def load_dotenv(env_path: Path) -> None:
    """轻量读取 .env 文件到 os.environ（不覆盖已有环境变量）。"""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def extract_json_block(text: str) -> Dict[str, Any]:
    """从模型输出中提取 JSON 对象（兼容 ```json ... ``` 代码块）。"""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError(f"无法从模型返回中解析合法 JSON，原始内容前 300 字：{text[:300]}")


class DeepSeekClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        vision_model: Optional[str] = None,
        text_model: Optional[str] = None,
        reasoner_model: Optional[str] = None,
        timeout: int = 120,
    ) -> None:
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "").strip()
        self.base_url = (base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")).rstrip("/")
        self.vision_model = vision_model or os.environ.get("DEEPSEEK_VISION_MODEL", "deepseek-flash")
        self.text_model = text_model or os.environ.get("DEEPSEEK_TEXT_MODEL", "deepseek-flash")
        self.reasoner_model = reasoner_model or os.environ.get("DEEPSEEK_REASONER_MODEL", "deepseek-v4-pro")
        self.timeout = timeout
        self.ssl_context = _build_ssl_context()

    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("sk-xxxx"))

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("未检测到有效的 DEEPSEEK_API_KEY，请先在 .env 文件中填入真实密钥。")

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DeepSeek API 请求失败 (HTTP {exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"无法连接 DeepSeek API ({url}): {exc.reason}") from exc

    def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: Optional[float] = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        chosen_model = model or self.text_model
        payload: Dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        # deepseek-reasoner 部分版本不建议传 temperature
        if temperature is not None and "reasoner" not in chosen_model:
            payload["temperature"] = temperature

        data = self._post("chat/completions", payload)
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"DeepSeek API 返回缺少 choices: {data}")
        return choices[0]["message"].get("content", "")

    def vision_extract(self, image_path: Path, prompt: str) -> str:
        mime, _ = mimetypes.guess_type(str(image_path))
        if not mime:
            mime = "image/png"
        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ]
        return self.chat(messages=messages, model=self.vision_model, temperature=0.1, max_tokens=4096)

    def check_models(self) -> Dict[str, Any]:
        """快速检查 API 连通性与可用模型列表。"""
        if not self.is_configured():
            raise RuntimeError("未检测到有效的 DEEPSEEK_API_KEY。")
        url = f"{self.base_url}/models"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=30, context=self.ssl_context) as resp:
            return json.loads(resp.read().decode("utf-8"))
