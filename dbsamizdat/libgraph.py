from collections import Counter
from functools import reduce
from itertools import chain
from operator import or_
from typing import Iterable

from toposort import CircularDependencyError, toposort

from dbsamizdat.loader import SamizType, filter_sds
from dbsamizdat.samizdat import Samizdat, SamizdatWithSidekicks

from .exceptions import DanglingReferenceError, DependencyCycleError, NameClashError, TypeConfusionError


def gen_edges(samizdats: Iterable[Samizdat]):
    for sd in samizdats:
        for n2 in sd.fqdeps_on():
            yield (n2, sd.fq())


def gen_autorefresh_edges(
    samizdats: Iterable[Samizdat],
):
    """
    R
    """
    for sd in samizdats:
        if hasattr(sd, "refresh_triggers"):
            yield (sd, sd.fq())


def gen_unmanaged_edges(samizdats: Iterable[Samizdat]):
    for sd in samizdats:
        for n2 in sd.fqdeps_on_unmanaged():
            yield (n2, sd.fq())


def node_dump(samizdats: Iterable[Samizdat]):
    """
    All nodes (managed or unmanaged)
    """
    return reduce(or_, (sd.fqdeps_on_unmanaged() | {sd.fq()} for sd in samizdats))


def unmanaged_refs(samizdats: Iterable[Samizdat | SamizdatWithSidekicks]):
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


def depsort(samizdats: Iterable[SamizType]):
    """
    Topologically sort samizdats
    """
    samizdat_map = {sd.fq(): sd for sd in samizdats}
    depmap = {sd.fq(): sd.fqdeps_on() for sd in samizdats}
    toposorted = toposort(depmap)

    return [samizdat_map[name] for name in chain(*toposorted)]


def depsort_with_sidekicks(samizdats: Iterable[SamizType]):
    """
    Injects "sidekicks" ino the topologically sorted
    samizdats list
    """
    returns: list[SamizType] = []
    heads = {sd.head_id() for sd in samizdats}

    for samizdat in depsort(samizdats):
        returns.append(samizdat)
        if hasattr(samizdat, "sidekicks"):
            sd: SamizdatWithSidekicks = samizdat  # Declare the type for mypy
            for kick in sd.sidekicks():
                if filter_sds(kick) and kick.head_id() not in heads:
                    returns.append(kick)
                    heads.add(kick.head_id())
    return returns


def sanity_check(samizdats: Iterable[SamizType]) -> Iterable[SamizType]:
    """
    Checks for a number of invalid conditions on the Samizdat tree
    """
    for sd in samizdats:
        # This raises an "UnsuitableNameError" if the
        # "name" is something Postgres might not handle well
        sd.validate_name()
    sd_fqs = set(sd.fq() for sd in samizdats)
    sd_deps = set(chain(*(sd.fqdeps_on() for sd in samizdats)))
    sd_deps_unmanaged = set(chain(*(sd.deps_on_unmanaged for sd in samizdats)))

    # are there any classes with ambiguous DB identity?
    cnt = Counter((sd.db_object_identity() for sd in samizdats))
    if nonunique := [db_id for db_id, count in cnt.items() if count > 1]:
        raise NameClashError("Non-unique DB entities specified: %s" % nonunique)

    # check if all declared samizdat deps are present
    if undeclared := sd_deps - sd_fqs:
        raise DanglingReferenceError(f"Nonexistent dependencies referenced: {undeclared}")

    # assert none of the declared unmanaged deps are declared samizdat
    if confused := sd_deps_unmanaged.intersection(sd_fqs):
        raise TypeConfusionError(f"Samizdat entity is also declared as *unmanaged* dependency: {confused}")

    if selfreffaulty := {sd for sd in samizdats if sd.fq() in sd.fqdeps_on()}:
        raise DependencyCycleError("Self-referential dependency", (selfreffaulty.pop(),))

    # cycle detection - other levels; toposort will raise an exception if there's one
    sdfqmap = {sd.fq(): sd for sd in samizdats}
    try:
        _ = depsort_with_sidekicks(samizdats)
    except CircularDependencyError as ouch:
        cyclists = tuple(map(sdfqmap.get, ouch.data.keys()))
        raise DependencyCycleError("Dependency cycle detected", cyclists)
    return samizdats
