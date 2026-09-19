"""Import every module's models here, once, so they register on Base.metadata.

`migrations/env.py` (autogenerate, and the RLS coverage test's `tenant_table_names()`)
and `tests/test_rls_coverage.py` both just `import app.modules.registry` instead of
each maintaining their own list -- add a model module here when you add a domain
module, not in two places.
"""

from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.catalog.models import product as product_models  # noqa: F401
from app.modules.custom.models import field_definition as field_definition_models  # noqa: F401
from app.modules.gateway.models import access_token as access_token_models  # noqa: F401
from app.modules.gateway.models import call_log as call_log_models  # noqa: F401
from app.modules.gateway.models import entitlement as entitlement_models  # noqa: F401
from app.modules.inventory.models import location as location_models  # noqa: F401
from app.modules.inventory.models import stock_move as stock_move_models  # noqa: F401
from app.modules.parties.models import customer as customer_models  # noqa: F401
from app.modules.parties.models import supplier as supplier_models  # noqa: F401
from app.modules.purchasing.models import purchase_order as purchase_order_models  # noqa: F401
from app.modules.sales.models import sales_order as sales_order_models  # noqa: F401
