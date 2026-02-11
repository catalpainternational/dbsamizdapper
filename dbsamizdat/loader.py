import inspect
from collections.abc import Iterable
from importlib import import_module
from importlib.util import find_spec
from logging import getLogger
from typing import Any, TypeGuard

from dbsamizdat.samizdat import (
    Samizdat,
    SamizdatFunction,
    SamizdatMaterializedModel,
    SamizdatMaterializedQuerySet,
    SamizdatMaterializedView,
    SamizdatModel,
    SamizdatQuerySet,
    SamizdatTable,
    SamizdatTrigger,
    SamizdatView,
)

type SamizType = type[
    Samizdat
    | SamizdatFunction
    | SamizdatMaterializedModel
    | SamizdatMaterializedQuerySet
    | SamizdatMaterializedView
    | SamizdatModel
    | SamizdatQuerySet
    | SamizdatTable
    | SamizdatTrigger
    | SamizdatView
]

type SamizTypes = set[SamizType]

logger = getLogger(__name__)

AUTOLOAD_MODULENAME = "dbsamizdat_defs"


def filter_sds(inputklass: Any) -> TypeGuard[SamizType]:
    """
    Returns subclasses of subclasses of "samizdat"
    These are the classes which would be user-specified
    """
    subclasses_of = (
        SamizdatFunction,
        SamizdatMaterializedModel,
        SamizdatMaterializedQuerySet,
        SamizdatMaterializedView,
        SamizdatModel,
        SamizdatQuerySet,
        SamizdatTable,
        SamizdatTrigger,
        SamizdatView,
    )
    return inspect.isclass(inputklass) and issubclass(inputklass, subclasses_of) and inputklass not in subclasses_of


def get_samizdats() -> Iterable[SamizType]:
    """
    Returns all subclasses of "Samizdat"
    where they are not considered abstract
    """

    def all_subclasses(cls=Samizdat):
        subs = cls.__subclasses__()
        yield from filter(filter_sds, subs)
        for c in subs:
            yield from all_subclasses(c)

    unique: dict[str, SamizType] = {}
    for elem in all_subclasses():
        unique.setdefault(elem.definition_hash(), elem)
    yield from unique.values()


def samizdats_in_module(mod) -> SamizTypes:
    """
    Returns the samizdat instances in a given module
    """
    return {thing for _, thing in inspect.getmembers(mod) if filter_sds(thing)}


def samizdats_in_app(app_name: str):
    """
    Returns the samizdat instances in a given app_name
    """
    module_name = f"{app_name}.{AUTOLOAD_MODULENAME}"
    spec = find_spec(module_name)
    if spec:
        try:
            module = import_module(module_name)
            samizdats = list(samizdats_in_module(module))
            if samizdats:
                yield from samizdats
            else:
                logger.warning(f"Module {module_name} found but contains no valid Samizdat classes")
        except ImportError as e:
            logger.warning(f"Failed to import {module_name}: {e}")
        except Exception as e:
            logger.warning(f"Error loading samizdats from {module_name}: {e}")
    else:
        logger.warning(f"Module {module_name} not found by find_spec")


def autodiscover_samizdats():
    """
    Search Django apps for "dbsamizdat_defs" files containing Samizdat models.
    Also includes modules specified in DBSAMIZDAT_MODULES setting.

    Yields:
        SamizType: Samizdat classes found in apps and DBSAMIZDAT_MODULES
    """
    try:
        from django.conf import settings
        if not settings.configured:
            logger.warning("Django settings not configured, skipping autodiscovery")
            return
    except ImportError:
        logger.warning("Django not available, skipping autodiscovery")
        return

    logger.warning(f"Starting autodiscovery with INSTALLED_APPS: {settings.INSTALLED_APPS}")

    # First, discover from installed apps
    total_found = 0
    for app in settings.INSTALLED_APPS:
        app_samizdats = list(samizdats_in_app(app))
        if app_samizdats:
            logger.warning(f"Found {len(app_samizdats)} samizdats in app {app}: {[str(s) for s in app_samizdats]}")
            total_found += len(app_samizdats)
            yield from app_samizdats
        else:
            logger.warning(f"No samizdats found in app {app}")

    logger.warning(f"Total samizdats found from apps: {total_found}")

    # Then, include modules from DBSAMIZDAT_MODULES setting
    django_sdmodules = getattr(settings, "DBSAMIZDAT_MODULES", [])
    if django_sdmodules:
        logger.warning(f"Checking DBSAMIZDAT_MODULES: {django_sdmodules}")
        for sdmod in django_sdmodules:
            try:
                module = import_module(sdmod)
                module_samizdats = list(samizdats_in_module(module))
                if module_samizdats:
                    logger.warning(f"Found {len(module_samizdats)} samizdats in module {sdmod}: {[str(s) for s in module_samizdats]}")
                    yield from module_samizdats
                else:
                    logger.warning(f"No samizdats found in DBSAMIZDAT_MODULES entry {sdmod}")
            except ImportError as e:
                logger.warning(f"Failed to import DBSAMIZDAT_MODULES entry {sdmod}: {e}")
            except Exception as e:
                logger.warning(f"Error loading samizdats from DBSAMIZDAT_MODULES entry {sdmod}: {e}")
