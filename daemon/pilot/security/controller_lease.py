"""Shared effect-controller lease for interactive, autonomous, and neural plans."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator


class ControllerLeaseBusy(ValueError):
    """A fail-closed controller could not acquire effect authority."""


@dataclass(frozen=True, slots=True)
class ControllerLeaseStatus:
    owner: str | None
    generation: int
    depth: int


class ControllerLeaseManager:
    """Serialize effectful plans while allowing neural acquisition to observe.

    Ordinary plans queue cooperatively. Neural commits never wait behind an
    action whose context may change; they fail closed and require a fresh
    preview instead.
    """

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._owner: str | None = None
        self._depth = 0
        self._generation = 0

    @asynccontextmanager
    async def claim(self, owner: str, *, wait: bool) -> AsyncIterator[ControllerLeaseStatus]:
        if not owner or len(owner) > 160 or any(ord(character) < 32 for character in owner):
            raise ValueError("controller lease owner is invalid")
        async with self._condition:
            while self._owner not in {None, owner}:
                if not wait:
                    raise ControllerLeaseBusy("another controller is executing; neural preview must be refreshed")
                await self._condition.wait()
            if self._owner is None:
                self._owner = owner
                self._generation += 1
            self._depth += 1
            status = ControllerLeaseStatus(self._owner, self._generation, self._depth)
        try:
            yield status
        finally:
            async with self._condition:
                if self._owner != owner or self._depth <= 0:
                    raise RuntimeError("controller lease ownership was corrupted")
                self._depth -= 1
                if self._depth == 0:
                    self._owner = None
                    self._condition.notify_all()

    async def status(self) -> ControllerLeaseStatus:
        async with self._condition:
            return ControllerLeaseStatus(self._owner, self._generation, self._depth)
