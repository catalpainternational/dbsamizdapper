import inspect
from importlib import import_module
from importlib.util import find_spec
from logging import getLogger
from typing import Iterable

from dbsamizdat.samizdat import Samizdat, SamizdatFunction, SamizdatMaterializedView, SamizdatTrigger, SamizdatView
from dbsamizdat.samtypes import ProtoSamizdat

excludelist = {
    Samizdat,
    SamizdatFunction,
    SamizdatView,
    SamizdatMaterializedView,
    SamizdatTrigger,
}

logger = getLogger(__name__)

AUTOLOAD_MODULENAME = "dbsamizdat_defs"


def get_samizdats() -> set[Samizdat]:
    """
    Returns all subclasses of "Samizdat"
    where they are not considered abstract
    """

    def all_subclasses(cls):
        return set(cls.__subclasses__()).union([s for c in cls.__subclasses__() for s in all_subclasses(c)])

    return all_subclasses(Samizdat).difference(excludelist)


def samizdats_in_module(mod):
    """
    Returns the samizdat instances in a given module
    """
    for _, thing in inspect.getmembers(mod):
        if inspect.isclass(thing) and ProtoSamizdat in thing.mro() and thing not in excludelist:
            yield thing


def samizdats_in_app(app_name: str):
    """
    Returns the samizdat instances in a given app_name
    """
    if find_spec(f"{app_name}.{AUTOLOAD_MODULENAME}"):
        module = import_module(f"{app_name}.{AUTOLOAD_MODULENAME}")
        yield from samizdats_in_module(module)


def autodiscover_samizdats() -> Iterable[Samizdat]:
    """
    Search Django apps for "dbsamizdat_defs" files containing Samizdat models
    """
    from django.conf import settings

    for app in settings.INSTALLED_APPS:
        yield from samizdats_in_app(app)
