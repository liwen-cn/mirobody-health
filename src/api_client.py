import os
import json
import base64
import urllib.request
import ssl
import re
import subprocess

def load_env():
    env_vars = {}
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip("'\"")
    return env_vars

def call_deepseek_vision(image_path, prompt, api_key):
    """Call DeepSeek API with an image and text prompt."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with open(image_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode("utf-8")

    # Determine mime type
    mime = "image/jpeg"
    if image_path.lower().endswith(".png"):
        mime = "image/png"

    payload = {
        "model": "deepseek-flash",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_img}"}}
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": 2048
    }

    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        data=json.dumps(payload).encode("utf-8")
    )

    with urllib.request.urlopen(req, context=ctx) as resp:
        res = json.loads(resp.read().decode())
        return res["choices"][0]["message"]["content"]

def call_deepseek_flash(prompt, api_key, system_prompt=None, json_mode=True, max_tokens=16384, timeout=240, disable_thinking=False):
    """Call DeepSeek-Flash (V4.1-Flash) for structured risk mining and food-therapy reasoning."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "deepseek-flash",
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if disable_thinking:
        payload["thinking"] = {"type": "disabled"}

    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        data=json.dumps(payload).encode("utf-8")
    )

    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        choice = res["choices"][0]
        content = choice["message"]["content"]
        finish_reason = choice.get("finish_reason", "")
        if json_mode and finish_reason == "length" and not disable_thinking:
            # Retry with thinking disabled so the full token budget goes to valid JSON
            return call_deepseek_flash(
                prompt, api_key,
                system_prompt=system_prompt,
                json_mode=True,
                max_tokens=max_tokens,
                timeout=timeout,
                disable_thinking=True,
            )
        return content

def call_deepseek_reasoner(prompt, api_key):
    """Backward-compatible wrapper routed to deepseek-flash."""
    return call_deepseek_flash(prompt, api_key, json_mode=False, max_tokens=4096)

