# Import all adapters so their @register decorators execute.
# Adding a new source: create the module, then add its import here.
from app.core.sources import adzuna as _adzuna  # noqa: F401
from app.core.sources import ashby as _ashby  # noqa: F401
from app.core.sources import greenhouse as _greenhouse  # noqa: F401
from app.core.sources import himalayas as _himalayas  # noqa: F401
from app.core.sources import hn_whoishiring as _hn  # noqa: F401
from app.core.sources import jsonld as _jsonld  # noqa: F401
from app.core.sources import lever as _lever  # noqa: F401
from app.core.sources import reed as _reed  # noqa: F401
from app.core.sources import remoteok as _remoteok  # noqa: F401
from app.core.sources import remotive as _remotive  # noqa: F401
