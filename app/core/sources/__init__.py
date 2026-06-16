# Import all adapters so their @register decorators execute.
# Adding a new source: create the module, then add its import here.
from app.core.sources import adzuna as _adzuna  # noqa: F401
