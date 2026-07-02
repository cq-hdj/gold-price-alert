#!/usr/bin/env python3
"""拉取 FreeJK 金价，定时推送到企业微信群机器人。"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

GOLD_API = "https://api.freejk.com/shuju/jinjia/"
STATE_FILE = Path(os.environ.get("STATE_FILE", ".gold_state.json"))
TZ = ZoneInfo(os.environ.get("TIMEZONE", "Asia/Shanghai"))


def fetch_gold_price() -> dict:
    req = urllib.request.Request(GOLD_API, headers={"User-Agent": "gold-price-alert/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode())
    if body.get("status") != "success":
        raise RuntimeError(f"API 返回异常: {body}")
    return body["data"]


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def format_delta(last_price: Optional[float], price: float) -> Tuple[str, str, str]:
    if last_price is None:
        return "首次记录", "info", "—"
    delta = price - last_price
    pct = (delta / last_price) * 100 if last_price else 0
    if delta > 0:
        return f"+{delta:.2f} 元/克 (+{pct:.3f}%)", "warning", "上涨"
    if delta < 0:
        return f"{delta:.2f} 元/克 ({pct:.3f}%)", "info", "下跌"
    return "0.00 元/克 (0.000%)", "comment", "持平"


def build_markdown(data: dict, last_price: float | None, check_time: datetime) -> str:
    price = float(data["price"])
    delta_text, color, trend = format_delta(last_price, price)
    intl_price = data.get("international_price", "—")
    intl_unit = data.get("international_unit", "USD/oz")

    # 粗算国际金价折合人民币/克（仅参考，按 31.1035 克/盎司）
    cny_per_gram_hint = ""
    try:
        usd_oz = float(intl_price)
        ref_cny = usd_oz * 7.25 / 31.1035
        cny_per_gram_hint = f"\n> 国际金价折算约：<font color=\"comment\">{ref_cny:.2f} 元/克</font>（按 7.25 汇率估算，仅供参考）"
    except (TypeError, ValueError):
        pass

    return (
        "## 黄金行情定时播报\n"
        f"> 品种：**{data.get('symbol', '上海黄金现货')}**\n"
        f"> 现价：<font color=\"{color}\">**{price:.2f} 元/克**</font>\n"
        f"> 较上次：<font color=\"{color}\">{delta_text}</font>（{trend}）\n"
        f"> 国际现货：**{intl_price} {intl_unit}**"
        f"{cny_per_gram_hint}\n"
        f"> 行情更新时间：{data.get('update_time', '—')}\n"
        f"> 接口缓存时间：{data.get('timestamp', '—')}\n"
        f"> 本次检查时间：{check_time.strftime('%Y-%m-%d %H:%M:%S')}（北京时间）\n"
        f"> 推送频率：每 30 分钟 · 数据源 [FreeJK](https://freejk.com/api/47)"
    )


def push_wecom(webhook: str, content: str) -> None:
    payload = json.dumps(
        {"msgtype": "markdown", "markdown": {"content": content}},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())
    if result.get("errcode") != 0:
        raise RuntimeError(f"企业微信推送失败: {result}")


def main() -> int:
    webhook = os.environ.get("WECOM_WEBHOOK", "").strip()
    if not webhook:
        print("ERROR: 请设置环境变量 WECOM_WEBHOOK")
        return 1

    data = fetch_gold_price()
    price = float(data["price"])
    check_time = datetime.now(TZ)

    state = load_state()
    last_price = state.get("last_price")
    if last_price is not None:
        last_price = float(last_price)

    content = build_markdown(data, last_price, check_time)
    push_wecom(webhook, content)
    print("已推送企业微信")

    state["last_price"] = price
    state["last_api_update"] = data.get("update_time")
    state["last_check_at"] = check_time.isoformat()
    state["last_push_at"] = check_time.isoformat()
    save_state(state)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (urllib.error.URLError, TimeoutError, RuntimeError) as e:
        print(f"ERROR: {e}")
        raise SystemExit(1)
