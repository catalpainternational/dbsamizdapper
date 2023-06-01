from logging import getLogger

from dbsamizdat.samizdat import (
    Samizdat,
    SamizdatFunction,
    SamizdatMaterializedView,
    SamizdatTrigger,
    SamizdatView,
)

logger = getLogger(__name__)

AUTOLOAD_MODULENAME = "dbsamizdat_defs"


def get_samizdats() -> set[Samizdat]:
    """
    Returns all subclasses of "Samizdat"
    where they are not considered "abstract"
    """

    def all_subclasses(cls):
        return set(cls.__subclasses__()).union(
            [s for c in cls.__subclasses__() for s in all_subclasses(c)]
        )

    excludelist = {
        Samizdat,
        SamizdatFunction,
        SamizdatView,
        SamizdatMaterializedView,
        SamizdatTrigger,
    }

    return all_subclasses(Samizdat).difference(excludelist)
