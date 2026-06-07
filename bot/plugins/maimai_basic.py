import random

import httpx
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent

help_cmd = on_command("舞萌帮助", aliases={"maimai帮助", "maihelp"}, priority=5)
ping_cmd = on_command("舞萌ping", aliases={"maiping"}, priority=5)
recommend_cmd = on_command("今日推荐", aliases={"mai推荐"}, priority=5)
recommend_by_player_cmd = on_command("训练推荐", aliases={"mai训练推荐"}, priority=5)


@help_cmd.handle()
async def _() -> None:
    await help_cmd.finish(
        "可用命令：\n"
        "1) 舞萌ping\n"
        "2) b50分析 用户名\n"
        "3) b50分析 qq:123456\n"
        "4) b50摘要 用户名\n"
        "5) 今日推荐\n"
        "6) 训练推荐 用户名\n"
        "7) b50分析 用户名 mode:s4\n"
        "8) b50摘要 用户名 mode:s4\n"
    )


@ping_cmd.handle()
async def _(event: MessageEvent) -> None:
    await ping_cmd.finish(f"pong, user={event.get_user_id()}")


@recommend_cmd.handle()
async def _() -> None:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get("http://127.0.0.1:8000/knowledge/songs")
        if resp.status_code != 200:
            await recommend_cmd.finish(f"推荐失败：{resp.text}")
            return
        data = resp.json()
    except httpx.HTTPError as exc:
        await recommend_cmd.finish(f"后端不可用：{exc}")
        return

    items = data.get("items", [])
    if not items:
        await recommend_cmd.finish("当前知识库暂无可推荐谱面。")
        return

    sample = random.sample(items, k=min(3, len(items)))
    lines = [
        f"- {song.get('title', '-')}"
        f" | {song.get('difficulty', '-')}"
        f" | {song.get('level', '-')}"
        f" | DS {song.get('ds', '-')}"
        for song in sample
    ]
    await recommend_cmd.finish("今日推荐谱面：\n" + "\n".join(lines))


@recommend_by_player_cmd.handle()
async def _(event: MessageEvent) -> None:
    text = str(event.get_message()).strip()
    if not text:
        await recommend_by_player_cmd.finish("请输入用户名或 qq:123456，例如：训练推荐 FHGY")
        return

    payload = {"b50": "1"}
    if text.startswith("qq:"):
        payload["qq"] = text.replace("qq:", "", 1)
    else:
        payload["username"] = text

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post("http://127.0.0.1:8000/analysis/recommend", json=payload)
        if resp.status_code != 200:
            await recommend_by_player_cmd.finish(f"推荐失败：{resp.text}")
            return
        data = resp.json()
    except httpx.HTTPError as exc:
        await recommend_by_player_cmd.finish(f"后端不可用：{exc}")
        return

    items = data.get("items", [])
    if not items:
        await recommend_by_player_cmd.finish("没有可推荐曲目。")
        return

    lines = [
        f"- {song.get('title', '-')}"
        f" | {song.get('difficulty', '-')}"
        f" | {song.get('level', '-')}"
        f" | DS {song.get('ds', '-')}"
        for song in items[:5]
    ]
    await recommend_by_player_cmd.finish(
        f"玩家: {data.get('player_id', '-')}\n"
        f"模型: {data.get('evaluation_model', '-')}\n"
        f"W值: {data.get('w_tier', '-')}\n"
        f"短板维度: {'/'.join(data.get('shortfalls', []))}\n"
        f"训练推荐:\n" + "\n".join(lines)
    )
