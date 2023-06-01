from .samtypes import entitypes  # noqa: F401
from .samizdat import (
    SamizdatFunction,  # noqa: F401
    SamizdatMaterializedView,  # noqa: F401
    SamizdatTrigger,  # noqa: F401
    SamizdatView,  # noqa: F401
)

default_app_config = "dbsamizdat.apps.DBSamizdatConfig"  # For Django < 4.0
