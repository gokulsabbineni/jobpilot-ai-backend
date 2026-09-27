from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ProviderResult:
    provider: str
    items: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class DiscoveryProvider(Protocol):
    name: str

    async def discover(self, query: str | None = None, limit: int = 100) -> ProviderResult:
        ...


class ApplicationProvider(Protocol):
    name: str

    def supports(self, url: str, source: str | None = None) -> bool:
        ...

    async def apply(self, db, user, application):
        ...
