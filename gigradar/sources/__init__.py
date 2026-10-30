"""Job sources.

Each source implements the :class:`gigradar.models.Source` interface. The
``build_sources`` factory maps config names to instances, so enabling/disabling
a source is just editing the ``sources`` list in config.
"""

from __future__ import annotations

from ..models import Source
from .remoteok import RemoteOKSource
from .remotive import RemotiveSource
from .weworkremotely import WeWorkRemotelySource
from .reddit import RedditForHireSource

_REGISTRY = {
    RemoteOKSource.name: RemoteOKSource,
    RemotiveSource.name: RemotiveSource,
    WeWorkRemotelySource.name: WeWorkRemotelySource,
    RedditForHireSource.name: RedditForHireSource,
}


def build_sources(names: list[str]) -> list[Source]:
    """Instantiate enabled sources by name, ignoring unknown entries."""
    out: list[Source] = []
    for n in names:
        cls = _REGISTRY.get(n.lower().strip())
        if cls is not None:
            out.append(cls())
    return out


def available_source_names() -> list[str]:
    return list(_REGISTRY.keys())
