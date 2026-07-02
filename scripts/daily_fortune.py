#!/usr/bin/env python3
"""每日运势：黄历 + 个人星座生肖 + 夫妻相处，推送到企业微信。"""

from __future__ import annotations

import hashlib
import json
import os
import random
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from lunar_python import Lunar, Solar

ROOT = Path(__file__).resolve().parent.parent
PEOPLE_FILE = ROOT / "config" / "people.json"
TZ = ZoneInfo(os.environ.get("TIMEZONE", "Asia/Shanghai"))

DIRECTION_MAP = {
    "坎": "正北", "坤": "西南", "震": "正东", "巽": "东南",
    "中": "中央", "乾": "西北", "兑": "正西", "艮": "东北", "离": "正南",
}

COLORS = ["红色", "橙色", "黄色", "绿色", "青色", "蓝色", "紫色", "白色", "金色", "银色", "粉色", "米色"]
CAREER_TIPS = [
    "适合主动推进手头项目，沟通效率较高。",
    "宜先整理计划再行动，避免急躁决策。",
    "适合学习新技能或复盘总结，厚积薄发。",
    "团队协作运佳，可多请教前辈意见。",
    "独立完成任务更顺，少卷入是非讨论。",
    "适合处理细节与文档，认真易获认可。",
    "创意灵感不错，可尝试提出新方案。",
    "稳字当头，按既定节奏推进即可。",
]
LOVE_TIPS_M = [
    "多表达关心，一句暖心话胜过千言万语。",
    "宜安排小惊喜，增进亲密感。",
    "倾听对方想法，少讲道理多共情。",
    "适合共进晚餐或散步，氛围融洽。",
]
LOVE_TIPS_F = [
    "心情较细腻，宜直接说出真实需求。",
    "适合分享日常小事，拉近距离。",
    "给对方一点空间，也留一点给自己。",
    "温柔坚定表达立场，关系更稳定。",
]
WEALTH_TIPS = [
    "财运平稳，宜记账理财，避免冲动消费。",
    "有小额进账机会，不宜重仓冒险。",
    "适合整理账单，控制非必要开支。",
    "投资需谨慎，多听专业意见。",
    "正财为主，踏实工作比投机更可靠。",
]
HEALTH_TIPS = [
    "注意作息，避免熬夜。",
    "多喝水，少油腻，肠胃宜清淡。",
    "适合轻度运动，如散步、拉伸。",
    "注意肩颈放松，久坐记得起身。",
    "情绪宜疏导，别把压力闷在心里。",
]
COUPLE_TIPS = [
    "宜一起制定小目标，例如周末出行或家庭计划。",
    "宜坦诚交流感受，忌冷战隔夜。",
    "宜各退一步，小事不较真。",
    "宜共同做家务或做饭，增进默契。",
    "忌在疲惫时讨论敏感话题，选轻松时段深聊。",
    "宜互相肯定，一句感谢能化解不少 friction。",
]


def load_people() -> List[Dict[str, Any]]:
    with open(PEOPLE_FILE, encoding="utf-8") as f:
        return json.load(f)


def person_profile(person: Dict[str, Any]) -> Dict[str, Any]:
    lunar = Lunar.fromYmd(person["lunar_year"], person["lunar_month"], person["lunar_day"])
    solar = lunar.getSolar()
    return {
        "name": person["name"],
        "gender": person["gender"],
        "role": person.get("role", ""),
        "lunar_text": f"农历{lunar.getYearInChinese()}年{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}",
        "solar_text": solar.toYmd(),
        "sign": solar.getXingZuo() + "座" if not solar.getXingZuo().endswith("座") else solar.getXingZuo(),
        "shengxiao": lunar.getYearShengXiao(),
    }


def seeded_rng(key: str) -> random.Random:
    digest = hashlib.sha256(key.encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def stars(rng: random.Random) -> str:
    n = rng.randint(3, 5)
    return "★" * n + "☆" * (5 - n)


def pick(rng: random.Random, items: List[str]) -> str:
    return items[rng.randint(0, len(items) - 1)]


def build_person_fortune(profile: Dict[str, Any], today: date) -> Dict[str, Any]:
    key = f"{today.isoformat()}:{profile['name']}:{profile['sign']}:{profile['shengxiao']}"
    rng = seeded_rng(key)
    love_pool = LOVE_TIPS_M if profile["gender"] == "男" else LOVE_TIPS_F
    return {
        "profile": profile,
        "overall": stars(rng),
        "career": pick(rng, CAREER_TIPS),
        "love": pick(rng, love_pool),
        "wealth": pick(rng, WEALTH_TIPS),
        "health": pick(rng, HEALTH_TIPS),
        "lucky_color": pick(rng, COLORS),
        "lucky_number": str(rng.randint(1, 9)),
        "lucky_direction": pick(rng, list(DIRECTION_MAP.values())),
        "summary": pick(rng, [
            "保持平常心，顺势而为。",
            "今日贵人运在细节里，认真即可。",
            "宜柔不宜刚，以和为贵。",
            "专注当下，少忧未来。",
            "好运藏在耐心与真诚里。",
        ]),
    }


def build_almanac(today: date) -> Dict[str, Any]:
    solar = Solar.fromYmd(today.year, today.month, today.day)
    lunar = solar.getLunar()
    yi = lunar.getDayYi() or []
    ji = lunar.getDayJi() or []
    return {
        "solar": today.strftime("%Y年%m月%d日"),
        "weekday": "星期" + lunar.getWeekInChinese(),
        "lunar": f"农历{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}",
        "ganzhi": f"{lunar.getYearInGanZhi()}年 {lunar.getMonthInGanZhi()}月 {lunar.getDayInGanZhi()}日",
        "yi": "、".join(yi[:8]) if yi else "—",
        "ji": "、".join(ji[:8]) if ji else "—",
        "chong": lunar.getDayChongDesc() or "—",
        "sha": lunar.getDaySha() or "—",
        "xishen": DIRECTION_MAP.get(lunar.getDayPositionXi(), lunar.getDayPositionXi() or "—"),
        "caishen": DIRECTION_MAP.get(lunar.getDayPositionCai(), lunar.getDayPositionCai() or "—"),
        "fushen": DIRECTION_MAP.get(lunar.getDayPositionFu(), lunar.getDayPositionFu() or "—"),
    }


def build_couple_fortune(names: List[str], today: date) -> Dict[str, str]:
    rng = seeded_rng(f"couple:{today.isoformat()}:{':'.join(names)}")
    score = rng.randint(82, 98)
    return {
        "score": str(score),
        "yi": pick(rng, [t for t in COUPLE_TIPS if t.startswith("宜")]),
        "ji": pick(rng, [t for t in COUPLE_TIPS if t.startswith("忌")]),
        "tip": pick(rng, [
            "射手与天蝎的组合：一个直率一个深沉，互补在于「先说清楚 + 给足安全感」。",
            "虎与鼠的组合：行动派与机灵派搭档，大事商量、小事互信。",
            "夫妻运看「沟通方式」多于运势本身，今日适合把话说明白。",
        ]),
    }


def render_markdown(almanac: Dict[str, Any], fortunes: List[Dict[str, Any]], couple: Dict[str, str], now: datetime) -> str:
    lines = [
        f"## 🌅 今日运势 · {almanac['solar']} {almanac['weekday']}",
        f"> {almanac['lunar']} · {almanac['ganzhi']}",
        "",
        "### 📜 今日黄历",
        f"> **宜**：{almanac['yi']}",
        f"> **忌**：{almanac['ji']}",
        f"> **冲煞**：{almanac['chong']} · 煞{almanac['sha']}",
        f"> **喜神** {almanac['xishen']} · **财神** {almanac['caishen']} · **福神** {almanac['fushen']}",
        "",
    ]

    for f in fortunes:
        p = f["profile"]
        lines.extend([
            f"### 👤 {p['name']}（{p['role']}）· {p['sign']} · 属{p['shengxiao']}",
            f"> 生日 {p['lunar_text']}（阳历 {p['solar_text']}）",
            f"> **综合** {f['overall']}",
            f"> **事业** {f['career']}",
            f"> **感情** {f['love']}",
            f"> **财运** {f['wealth']}",
            f"> **健康** {f['health']}",
            f"> **幸运** 色 `{f['lucky_color']}` · 数字 `{f['lucky_number']}` · 方位 `{f['lucky_direction']}`",
            f"> **一句** {f['summary']}",
            "",
        ])

    lines.extend([
        "### 💑 夫妻今日",
        f"> **合拍指数** {couple['score']} / 100",
        f"> {couple['yi']}",
        f"> {couple['ji']}",
        f"> {couple['tip']}",
        "",
        f"> 推送时间 {now.strftime('%Y-%m-%d %H:%M')}（北京时间）· 仅供娱乐参考",
    ])
    return "\n".join(lines)


def push_wecom(webhook: str, content: str) -> None:
    payload = json.dumps({"msgtype": "markdown", "markdown": {"content": content}}, ensure_ascii=False).encode()
    req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())
    if result.get("errcode") != 0:
        raise RuntimeError(f"企业微信推送失败: {result}")


def main() -> int:
    webhook = os.environ.get("WECOM_WEBHOOK", "").strip()
    if not webhook:
        print("ERROR: 请设置 WECOM_WEBHOOK")
        return 1

    today = datetime.now(TZ).date()
    people = load_people()
    profiles = [person_profile(p) for p in people]
    fortunes = [build_person_fortune(p, today) for p in profiles]
    almanac = build_almanac(today)
    couple = build_couple_fortune([p["name"] for p in profiles], today)
    content = render_markdown(almanac, fortunes, couple, datetime.now(TZ))

    push_wecom(webhook, content)
    print("已推送今日运势")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as e:
        print(f"ERROR: {e}")
        raise SystemExit(1)
