"""Task-owned reentrant lock for nested connection and command transactions."""

import asyncio


class TaskLock:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._owner: asyncio.Task | None = None
        self._depth = 0

    def locked(self) -> bool:
        return self._lock.locked()

    async def __aenter__(self):
        task = asyncio.current_task()
        if self._owner is not task:
            await self._lock.acquire()
            self._owner = task
        self._depth += 1
        return self

    async def __aexit__(self, *_exc):
        self._depth -= 1
        if not self._depth:
            self._owner = None
            self._lock.release()
