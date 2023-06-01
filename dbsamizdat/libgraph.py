import typing
from collections import Counter
from functools import reduce
from itertools import chain
from operator import or_

from toposort import CircularDependencyError, toposort

from dbsamizdat.samizdat import Samizdat

from .exceptions import DanglingReferenceError, DependencyCycleError, NameClashError, TypeConfusionError
from .samtypes import HasRefreshTriggers, ProtoSamizdat


def gen_edges(samizdats: typing.Iterable[Samizdat]):
    for sd in samizdats:
        for n2 in sd.fqdeps_on():
            yield (n2, sd.fq())


def gen_autorefresh_edges(
    samizdats: typing.Iterable[ProtoSamizdat | HasRefreshTriggers],
):
    for sd in samizdats:
        if hasattr(sd, "refresh_triggers"):
            yield (sd, sd.fq())


def gen_unmanaged_edges(samizdats: typing.Iterable[Samizdat]):
    for sd in samizdats:
        for n2 in sd.fqdeps_on_unmanaged():
            yield (n2, sd.fq())


def node_dump(samizdats: typing.Iterable[Samizdat]):
    """
    All nodes (managed or unmanaged)
    """
    return reduce(or_, (sd.fqdeps_on_unmanaged() | {sd.fq()} for sd in samizdats))


def unmanaged_refs(samizdats: typing.Iterable[Samizdat | HasRefreshTriggers]):
    """
    All unmanaged nodes referenced
    """
    set_of_refs = set()
    for sd in samizdats:
        if hasattr(sd, "fqrefresh_triggers"):
            set_of_refs.update(sd.fqrefresh_triggers())
        if hasattr(sd, "fqdeps_on_unmanaged"):
            set_of_refs.update(sd.fqdeps_on_unmanaged())
    return set_of_refs


def subtree_nodes(samizdats: list[Samizdat], subtree_root):
    """
    All nodes depending on subtree_root (includes subtree_root)
    """

    def stn(subtree_root):
        yield subtree_root
        revdeps = (sd.fq() for sd in samizdats if (subtree_root in (sd.fqdeps_on() | sd.fqdeps_on_unmanaged())))
        yield from chain.from_iterable(map(stn, revdeps))

    return set(stn(subtree_root))


def subtree_depends(samizdats: list[Samizdat], roots):
    """
    Samizdats directly or indirectly depending on any root in roots
    """
    sdmap = {sd.fq(): sd for sd in samizdats}
    return reduce(
        or_,
        (
            set(
                filter(
                    None,
                    (sdmap.get(name) for name in subtree_nodes(samizdats, rootnode)),
                )
            )
            for rootnode in roots
        ),
        set(),
    )


def depsort(samizdats: typing.Iterable[Samizdat]):
    """
    Topologically sort samizdats
    """
    samizdat_map = {sd.fq(): sd for sd in samizdats}
    depmap = {sd.fq(): sd.fqdeps_on() for sd in samizdats}

    toposorted = toposort(depmap)

    return [samizdat_map[name] for name in chain(*(sorted(level) for level in toposorted))]


def depsort_with_sidekicks(samizdats: typing.Iterable[Samizdat]):
    return list(chain(*(sd.and_sidekicks() for sd in depsort(samizdats))))


def sanity_check(samizdats: typing.Iterable[Samizdat]):
    for sd in samizdats:
        sd.validate_name()
    sd_fqs = set(sd.fq() for sd in samizdats)
    sd_deps = set(chain(*(sd.fqdeps_on() for sd in samizdats)))
    sd_deps_unmanaged = set(chain(*(sd.deps_on_unmanaged for sd in samizdats)))

    # are there any classes with ambiguous DB identity?
    if len(sd_fqs) < len(list(samizdats)):
        cnt = Counter((sd.db_object_identity for sd in samizdats))
        nonunique = [db_id for db_id, count in cnt.items() if count > 1]
        if nonunique:
            raise NameClashError("Non-unique DB entities specified: %s" % nonunique)
    # check if all declared samizdat deps are present
    if not sd_deps.issubset(sd_fqs):
        raise DanglingReferenceError("Nonexistent dependencies referenced: %s" % (sd_deps - sd_fqs))
    # assert none of the declared unmanaged deps are declared samizdat
    confused = sd_deps_unmanaged.intersection(sd_fqs)
    if confused:
        raise TypeConfusionError("Samizdat entity is also declared as *unmanaged* dependency: %s" % confused)
    # cycle detection - top level
    selfreffaulty = {sd for sd in samizdats if sd.fq() in sd.deps_on}
    if selfreffaulty:
        raise DependencyCycleError("Self-referential dependency", (selfreffaulty.pop(),))
    # cycle detection - other levels; toposort will raise an exception if there's one
    sdfqmap = {sd.fq(): sd for sd in samizdats}
    try:
        _ = depsort_with_sidekicks(samizdats)
    except CircularDependencyError as ouch:
        cyclists = tuple(map(sdfqmap.get, ouch.data.keys()))
        raise DependencyCycleError("Dependency cycle detected", cyclists)
    return samizdats
