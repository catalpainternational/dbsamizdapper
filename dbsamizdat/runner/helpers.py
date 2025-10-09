"""
Helper functions for runner module.

This module contains utility functions used by the command runner:
- vprint: Conditional printing/logging
- timer: Timing generator for performance monitoring
- get_sds: Samizdat discovery and sorting
"""

import sys
from collections.abc import Generator
from logging import getLogger
from time import monotonic

from ..libgraph import depsort_with_sidekicks, sanity_check
from ..loader import SamizType, autodiscover_samizdats, get_samizdats
from .types import ArgType

logger = getLogger(__name__)
PRINTKWARGS = dict(file=sys.stderr, flush=True)


def vprint(args: ArgType, *pargs, **pkwargs):
    """
    Conditional print/log based on args settings.

    Args:
        args: ArgType with verbosity and log_rather_than_print settings
        *pargs: Arguments to print/log
        **pkwargs: Keyword arguments passed to print

    Behavior:
        - If log_rather_than_print: logs to logger
        - If verbosity > 0: prints to stderr
        - Otherwise: silent
    """
    if args.log_rather_than_print:
        logger.info(" ".join(map(str, pargs)))
    elif args.verbosity:
        print(*pargs, **PRINTKWARGS, **pkwargs)  # type: ignore


def timer() -> Generator[float, None, None]:
    """
    Generator to show time elapsed since the last iteration.

    Yields:
        float: Elapsed time in seconds since last yield

    Example:
        >>> t = timer()
        >>> next(t)  # Initialize
        0.0
        >>> # ... do work ...
        >>> next(t)  # Get elapsed time
        0.523
    """
    last = monotonic()
    while True:
        cur = monotonic()
        yield (cur - last)
        last = cur


def get_sds(in_django: bool = False, samizdats: list[SamizType] | None = None):
    """
    Get and validate samizdats from various sources.

    Samizdats may be defined by:
    - An explicit list (samizdats parameter)
    - Autodiscovery (default when not in Django)
    - Django module search (when in_django=True)

    Args:
        in_django: Whether to use Django autodiscovery
        samizdats: Optional explicit list of samizdat classes

    Returns:
        list[SamizType]: Samizdats sorted by dependency order

    Raises:
        NameClashError: If duplicate names detected
        DanglingReferenceError: If missing dependencies
        DependencyCycleError: If circular dependencies
        TypeConfusionError: If managed/unmanaged confusion

    Note:
        Runs sanity_check twice: before and after sorting.
        Includes auto-generated sidekicks (triggers, functions).
    """
    if samizdats:
        sds = set(samizdats)
    elif in_django:
        sds = set(autodiscover_samizdats())
    else:
        sds = set(get_samizdats())

    sanity_check(sds)
    sorted_sds = list(depsort_with_sidekicks(sds))
    sanity_check(sorted_sds)
    return sorted_sds
