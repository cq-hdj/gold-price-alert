#!/usr/bin/env python3
"""拉取上金所 AU9999 实时金价，定时推送到企业微信群机器人。"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

# 东方财富 · 上金所 AU9999 实时行情（与京东积存金等同口径的现货参考价）
SGE_API = (
    "https://push2.eastmoney.com/api/qt/stock/get"
    "?secid=118.AU9999&fields=f43,f44,f45,f46,f57,f58,f60,f170"
)
INTL_API = "https://aurumrates.com/api/v1/spot?metals=gold"
STATE_FILE = Path(os.environ.get("STATE_FILE", ".gold_state.json"))
TZ = ZoneInfo(os.environ.get("TIMEZONE", "Asia/Shanghai"))


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "gold-price-alert/2.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _cent_to_yuan(value: Any) -> Optional[float]:
    if value in (None, "-", ""):
        return None
    return round(float(value) / 100, 2)


def fetch_gold_price() -> Dict[str, Any]:
    body = _get_json(SGE_API)
    data = body.get("data") or {}
    if not data.get("f43"):
        raise RuntimeError(f"上金所行情返回异常: {body}")

    price = _cent_to_yuan(data["f43"])
    prev_close = _cent_to_yuan(data.get("f60"))
    change_pct = round(float(data.get("f170", 0)) / 100, 2) if data.get("f170") is not None else None

    intl_price = None
    intl_unit = "USD/oz"
    try:
        intl = _get_json(INTL_API)
        gold = (intl.get("data") or {}).get("gold") or {}
        intl_price = gold.get("price")
    except (urllib.error.URLError, TimeoutError, ValueError, RuntimeError):
        pass

    return {
        "symbol": data.get("f58") or "黄金9999",
        "code": data.get("f57") or "AU9999",
        "price": price,
        "open": _cent_to_yuan(data.get("f46")),
        "high": _cent_to_yuan(data.get("f44")),
        "low": _cent_to_yuan(data.get("f45")),
        "prev_close": prev_close,
        "change_pct": change_pct,
        "international_price": intl_price,
        "international_unit": intl_unit,
        "source": "东方财富 · 上金所 AU9999",
    }


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


def build_markdown(data: dict, last_price: Optional[float], check_time: datetime) -> str:
    price = float(data["price"])
    delta_text, color, trend = format_delta(last_price, price)

    vs_prev = ""
    if data.get("prev_close") is not None and data.get("change_pct") is not None:
        chg = float(data["price"]) - float(data["prev_close"])
        vs_prev = (
            f"\n> 较昨收：{chg:+.2f} 元/克 ({data['change_pct']:+.2f}%)"
            f"（昨收 {data['prev_close']:.2f}）"
        )

    intl_line = ""
    if data.get("international_price"):
        intl_line = f"\n> 国际现货（COMEX）：**{data['international_price']} {data['international_unit']}**"

    return (
        "## 黄金行情定时播报\n"
        f"> 品种：**{data['code']} {data['symbol']}**（上金所现货）\n"
        f"> 现价：<font color=\"{color}\">**{price:.2f} 元/克**</font>\n"
        f"> 今开/最高/最低：{data.get('open', '—')} / {data.get('high', '—')} / {data.get('low', '—')} 元/克"
        f"{vs_prev}\n"
        f"> 较上次推送：<font color=\"{color}\">{delta_text}</font>（{trend}）"
        f"{intl_line}\n"
        f"> 口径说明：与京东积存金、银行积存金同类的 **AU9999 现货参考价**，"
        f"非品牌金饰零售价（金店通常更高）\n"
        f"> 数据源：{data.get('source')}\n"
        f"> 检查时间：{check_time.strftime('%Y-%m-%d %H:%M:%S')}（北京时间）\n"
        f"> 推送频率：每 30 分钟"
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
    print(f"已推送企业微信，AU9999 现价 {price:.2f} 元/克")

    state["last_price"] = price
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
