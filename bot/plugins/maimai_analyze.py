import httpx
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message

b50_cmd = on_command("b50分析", aliases={"六维分析"}, priority=5)
b50_summary_cmd = on_command("b50摘要", aliases={"b50summary"}, priority=5)


def _parse_player_text(text: str) -> dict:
    payload = {"b50": "1", "evaluation_model": "legacy"}
    normalized = text.strip()
    if "mode:s4" in normalized:
        payload["evaluation_model"] = "s4"
        normalized = normalized.replace("mode:s4", "").strip()
    elif "mode:legacy" in normalized:
        payload["evaluation_model"] = "legacy"
        normalized = normalized.replace("mode:legacy", "").strip()
    if normalized.startswith("qq:"):
        payload["qq"] = normalized.replace("qq:", "", 1)
    else:
        payload["username"] = normalized
    return payload


def _rate_label(rate: str | None) -> str:
    mapping = {
        "sp": "S+",
        "ssp": "SS+",
        "sssp": "SSS+",
    }
    if not rate:
        return "-"
    r = rate.lower()
    return mapping.get(r, r.upper())


@b50_cmd.handle()
async def _(args: Message) -> None:
    text = args.extract_plain_text().strip()
    if not text:
        await b50_cmd.finish("请输入用户名或 qq:123456")
        return

    payload = _parse_player_text(text)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post("http://127.0.0.1:8000/analysis/b50", json=payload)
        if resp.status_code != 200:
            await b50_cmd.finish(f"分析失败：{resp.text}")
            return
        data = resp.json()
    except httpx.HTTPError as exc:
        await b50_cmd.finish(f"后端不可用：{exc}")
        return

    dims = data["radar"]["dimensions"]
    top = sorted(dims, key=lambda d: d["score"], reverse=True)[:2]
    weak = sorted(dims, key=lambda d: d["score"])[:2]
    b35_count = len(data.get("b35", []))
    b15_count = len(data.get("b15", []))
    msg = (
        f"玩家: {data['player_id']}\n"
        f"模型: {data.get('evaluation_model', '-')}\n"
        f"Rating: {data.get('rating')}\n"
        f"W值: {data.get('w_tier', '-')}\n"
        f"B35/B15: {b35_count}/{b15_count}\n"
        f"强项: {top[0]['name']}({top[0]['score']}) / {top[1]['name']}({top[1]['score']})\n"
        f"短板: {weak[0]['name']}({weak[0]['score']}) / {weak[1]['name']}({weak[1]['score']})\n"
        f"建议: {data['advice'][0]['detail']}"
    )
    await b50_cmd.finish(msg)


@b50_summary_cmd.handle()
async def _(args: Message) -> None:
    text = args.extract_plain_text().strip()
    if not text:
        await b50_summary_cmd.finish("请输入用户名或 qq:123456")
        return

    payload = _parse_player_text(text)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post("http://127.0.0.1:8000/analysis/b50", json=payload)
        if resp.status_code != 200:
            await b50_summary_cmd.finish(f"查询失败：{resp.text}")
            return
        data = resp.json()
    except httpx.HTTPError as exc:
        await b50_summary_cmd.finish(f"后端不可用：{exc}")
        return

    b50 = data.get("b50", [])
    if not b50:
        await b50_summary_cmd.finish("没有可展示的 B50 数据，请确认隐私设置或稍后重试。")
        return

    top_3 = b50[:3]
    lines = []
    for idx, item in enumerate(top_3, start=1):
        lines.append(
            f"{idx}. {item.get('title', '-')}"
            f" | {item.get('level_label', '-')}"
            f" | 达成 {item.get('achievements', '-')}"
            f" | 评价 {_rate_label(item.get('rate'))}"
            f" | RA {item.get('ra', '-')}"
        )

    await b50_summary_cmd.finish(
        f"玩家: {data.get('player_id', '-')}\n"
        f"模型: {data.get('evaluation_model', '-')}\n"
        f"Rating: {data.get('rating', '-')}\n"
        f"W值: {data.get('w_tier', '-')}\n"
        f"B35/B15: {len(data.get('b35', []))}/{len(data.get('b15', []))}\n"
        f"Top3:\n" + "\n".join(lines)
    )
