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
    if find_spec(f"{app_name}.{AUTOLOAD_MODULENAME}"):
        module = import_module(f"{app_name}.{AUTOLOAD_MODULENAME}")
        yield from samizdats_in_module(module)


def autodiscover_samizdats():
    """
    Search Django apps for "dbsamizdat_defs" files containing Samizdat models.
    Also includes modules specified in DBSAMIZDAT_MODULES setting.

    Yields:
        SamizType: Samizdat classes found in apps and DBSAMIZDAT_MODULES
    """
    from django.conf import settings

    # First, discover from installed apps
    for app in settings.INSTALLED_APPS:
        yield from samizdats_in_app(app)

    # Then, include modules from DBSAMIZDAT_MODULES setting
    django_sdmodules = getattr(settings, "DBSAMIZDAT_MODULES", [])
    for sdmod in django_sdmodules:
        module = import_module(sdmod)
        yield from samizdats_in_module(module)
