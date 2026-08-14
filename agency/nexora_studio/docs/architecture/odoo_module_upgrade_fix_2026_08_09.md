# Odoo Module Upgrade Fix (2026-08-09)

## Original Error
During the module upgrade process (`ir.module.module.button_immediate_upgrade`), Odoo 17 failed with the following traceback:
```
odoo.tools.convert.ParseError: while parsing file:/d:/odoo/custom-addons/agency/nexora_studio/views/connector_views.xml:216
Invalid view nexora.connector.search definition in nexora_studio/views/connector_views.xml
```

## Root Cause
The root cause of the error was twofold:
1. **RelaxNG validation failure on `<search>` views**: In Odoo 17, the `<group>` tag inside a `<search>` view does NOT support the `string` and `expand` attributes. The search view contained `<group expand="0" string="Group By">` which strictly violated `search_view.rng` validation checks.
2. **References to deleted models**: The `connector_views.xml` still contained UI components for `nexora.connector_marketplace` and `nexora.connector_repository` which were removed during the Phase 28 ADR-0050/0051 refactoring.

## Affected File
- `d:\ODOO\custom-addons\agency\nexora_studio\views\connector_views.xml`

## Exact Fix
1. **Search View Group**: Changed `<group expand="0" string="Group By">` to `<group name="group_by">` in `nexora.connector.search` to adhere to the Odoo 17 XML view definitions (`common.rng`). This resolved the RNG `RELAXNG_ERR_INVALIDATTR` error which caused `search_valid` to fail.
2. **Marketplace & Repo Views**: Completely deleted the `<record>` blocks for `view_nexora_connector_marketplace_list`, `action_nexora_connector_marketplace`, `view_nexora_connector_repository_list`, `action_nexora_connector_repository`, and their associated menu items from the XML.

## Verification
- **Module Upgrade**: Successfully ran `python community\odoo\odoo-bin -c configs\dev.conf -u nexora_studio --stop-after-init` with 0 failures or ParseErrors.
- **Odoo Functionality**: The Odoo server successfully rebuilt the registry and fully upgraded the module.
- **Regression Tests**: Ran the Phase 28 AAT and MCP regression tests successfully (`run_phase28_tests.py`), confirming that no core architectural logic was impacted by this UI fix.

---

# Operational Bug Fix: Connector Types Navigation

## Original Defect
After fixing the module upgrade, clicking the **Connector Types** menu in the Odoo UI caused a full page reload or blank screen instead of opening the `nexora.connector_type` list view.

## Root Cause Diagnosis
The Odoo 17 Web Client (OWL) ActionManager relies heavily on standard model fields (like `name` or the default `_rec_name`) when constructing breadcrumbs and default `search_read` list parameters.
The `nexora.connector_type` model:
1. Explicitly redefined Odoo's internal `display_name` field as a `fields.Char(string='Display Name', required=True)`.
2. Did not define a standard `name` field.
3. Specified `_order = 'display_name asc'`.

Because Odoo's core `models.Model` fundamentally treats `display_name` as a computed `store=False` field, the `_order = 'display_name asc'` directive caused the backend `_search` SQL generator to throw a `ValueError: Cannot convert nexora.connector_type.display_name to SQL because it is not stored`. This unhandled JSON-RPC traceback crashed the browser-side OWL client during route transition.

## Exact Fix
1. **`nexora_connector_type.py`**:
   - Renamed `display_name` field to `name = fields.Char(string='Name', required=True)`.
   - Updated `_order = 'name asc'`.
2. **`connector_views.xml`**:
   - Updated the list and form views for `nexora.connector_type` to use `<field name="name"/>` instead of `display_name`.
3. **`odoo_adapter.py`**:
   - Corrected the connector type search query from `[('code', '=', ctype_id)]` to `[('type_code', '=', ctype_id)]` to match the actual `type_code` field on the model.

## Verification
- **RPC Validation**: A raw python `env['nexora.connector_type'].search_read([], ['name', 'type_code'])` confirmed that the JSON-RPC backend successfully returns data without SQL compilation errors.
- **Module Upgrade**: Successfully re-ran the `odoo-bin -u nexora_studio` upgrade command without issues.
- **Phase 28 AAT Regression**: Re-ran the full Phase 28 suite (`python run_phase28_tests.py`); all 56 tests passed seamlessly in 11.75s, confirming total architectural compliance and operational readiness.
