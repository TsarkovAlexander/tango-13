import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator

from app.models import RunEvent, RunStatus


class RunStatusProjection:
    def __init__(self, queue_size: int = 100) -> None:
        self._queue_size = queue_size
        self._events: dict[str, deque[RunEvent]] = defaultdict(deque)
        self._subscribers: dict[str, set[asyncio.Queue[RunEvent]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def publish(self, event: RunEvent) -> None:
        async with self._lock:
            history = self._events[event.run_id]
            history.append(event)
            while len(history) > self._queue_size:
                history.popleft()

            subscribers = tuple(self._subscribers.get(event.run_id, ()))

        for queue in subscribers:
            queue.put_nowait(event)

    async def latest_status(self, run_id: str) -> RunStatus | None:
        async with self._lock:
            events = self._events.get(run_id)
            if not events:
                return None
            return events[-1].status

    async def events(self, run_id: str) -> AsyncIterator[RunEvent]:
        queue: asyncio.Queue[RunEvent] = asyncio.Queue(maxsize=self._queue_size)
        async with self._lock:
            history = list(self._events.get(run_id, ()))
            self._subscribers[run_id].add(queue)

        try:
            for event in history:
                yield event
                if event.status in {RunStatus.SUCCEEDED, RunStatus.FAILED}:
                    return

            while True:
                event = await queue.get()
                yield event
                if event.status in {RunStatus.SUCCEEDED, RunStatus.FAILED}:
                    return
        finally:
            async with self._lock:
                self._subscribers[run_id].discard(queue)
                if not self._subscribers[run_id]:
                    self._subscribers.pop(run_id, None)
