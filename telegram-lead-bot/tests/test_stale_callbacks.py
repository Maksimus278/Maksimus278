import asyncio
import time
import types

from bot.handlers import _block_stale_costly_action, _is_costly_callback


def test_costly_prefixes():
    assert _is_costly_callback("vm:1")
    assert _is_costly_callback("call:1")
    assert _is_costly_callback("batch:send:1")
    assert not _is_costly_callback("status:contacted:1")
    assert not _is_costly_callback("cmd:next")


def test_stale_costly_requires_reconfirm():
    class Msg:
        def __init__(self, ts):
            self.date = types.SimpleNamespace(timestamp=lambda: ts)
            self.replies = []

        async def reply_text(self, text, **kw):
            self.replies.append(text)

    class Query:
        def __init__(self, msg):
            self.message = msg
            self.from_user = types.SimpleNamespace(id=1)

    class Ctx:
        def __init__(self, boot):
            self.application = types.SimpleNamespace(bot_data={"boot_wall": boot})
            self.user_data = {}

    async def run():
        boot = time.time()
        msg = Msg(boot - 120)
        q = Query(msg)
        ctx = Ctx(boot)
        assert await _block_stale_costly_action(q, ctx, "vm:999") is True
        assert msg.replies
        assert await _block_stale_costly_action(q, ctx, "vm:999") is False

    asyncio.run(run())
