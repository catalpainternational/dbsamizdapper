"""
Helper functions for runner module.

This module contains utility functions used by the command runner:
- vprint: Conditional printing/logging
- timer: Timing generator for performance monitoring
- get_sds: Samizdat discovery and sorting
- import_samizdat_modules: Import modules containing samizdat classes
"""

import sys
from collections.abc import Generator
from importlib import import_module
from logging import getLogger
from time import monotonic

from ..libgraph import depsort_with_sidekicks, sanity_check
from ..loader import SamizType, autodiscover_samizdats, get_samizdats, samizdats_in_module
from .types import ArgType

logger = getLogger(__name__)
PRINTKWARGS = {"file": sys.stderr, "flush": True}


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


def import_samizdat_modules(module_names: list[str]):
    """
    Import modules containing samizdat class definitions.

    Args:
        module_names: List of module names (e.g., ["myapp.views", "myapp.models"])

    Returns:
        list: List of imported module objects

    Raises:
        ImportError: If any module cannot be imported

    Example:
        >>> modules = import_samizdat_modules(["myapp.dbsamizdat_defs"])
        >>> samizdats = [sd for m in modules for sd in samizdats_in_module(m)]
    """
    modules = []
    for module_name in module_names:
        module = import_module(module_name) if module_name not in sys.modules else sys.modules[module_name]
        modules.append(module)
    return modules


def get_sds(
    in_django: bool = False,
    samizdats: list[SamizType] | None = None,
    samizdatmodules: list[str] | None = None,
):
    """
    Get and validate samizdats from various sources.

    Samizdats may be defined by:
    - An explicit list (samizdats parameter) - takes highest precedence
    - Module names (samizdatmodules parameter) - imports modules and discovers classes
    - Autodiscovery (default) - finds all imported subclasses or Django apps

    Args:
        in_django: Whether to use Django autodiscovery
        samizdats: Optional explicit list of samizdat classes (takes precedence)
        samizdatmodules: Optional list of module names to import and search

    Returns:
        list[SamizType]: Samizdats sorted by dependency order

    Raises:
        NameClashError: If duplicate names detected
        DanglingReferenceError: If missing dependencies
        DependencyCycleError: If circular dependencies
        TypeConfusionError: If managed/unmanaged confusion
        ImportError: If samizdatmodules contains invalid module names

    Note:
        Runs sanity_check twice: before and after sorting.
        Includes auto-generated sidekicks (triggers, functions).
        Empty samizdatmodules list falls back to autodiscovery.

    Example:
        >>> # Using explicit classes
        >>> samizdats = get_sds(samizdats=[MyView, MyTable])

        >>> # Using module names
        >>> samizdats = get_sds(samizdatmodules=["myapp.views", "myapp.models"])

        >>> # Using autodiscovery (finds all imported subclasses or Django apps)
        >>> samizdats = get_sds()
    """
    if samizdats:
        # Explicit list takes highest precedence
        sds = set(samizdats)
    elif samizdatmodules:
        # Import modules and discover samizdats within them
        # Note: Empty list or None means "not specified" (falls through to autodiscovery)
        modules = import_samizdat_modules(samizdatmodules)
        sds = set()
        for module in modules:
            sds.update(samizdats_in_module(module))
    elif in_django:
        sds = set(autodiscover_samizdats())
    else:
        # Autodiscovery: finds all imported Samizdat subclasses
        sds = set(get_samizdats())

    sanity_check(sds)
    sorted_sds = list(depsort_with_sidekicks(sds))
    sanity_check(sorted_sds)
    return sorted_sds
