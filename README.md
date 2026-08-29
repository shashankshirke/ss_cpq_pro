# SS CPQ Pro (Phase 1 — Sales Side Only)

A lightweight Configure-Price-Quote app for ERPNext/Frappe. Phase 1 covers
the sales side only: define attributes and groups, configure a product
through a guided Desk page, and generate a Sales Order. Configurable BOM
generation is deferred to Phase 2, but the `CPQ Configuration` doctype
already exists as the hook point for it.

## Architecture

- **CPQ Attribute** / **CPQ Attribute Value** — the attribute master (matches
  your original note: attribute-value pairs, type, and now price impact
  lives per-value or as a per-unit rate for Number attributes).
- **CPQ Attribute Group** / **CPQ Attribute Group Item** — groups of
  attributes that get applied to items (e.g. "T-Shirt Config" = Size + Color).
- **CPQ Constraint Rule** — simple `if / then` rules (Mandatory or Exclusion),
  scoped to an Attribute Group. Supports `=`, `!=`, `>`, `>=`, `<`, `<=` so
  numeric thresholds (e.g. "Length > 2000 → Frame = Heavy-Duty") work, not
  just discrete equality.
- **CPQ Configuration** / **CPQ Configuration Detail** — the configuration
  snapshot: what was selected, at what price, for which Sales Order. This is
  the audit trail, and the future anchor point for Phase 2 BOM generation.
- **Item.cpq_attribute_group** (custom field) — tells the configurator which
  attribute group applies to an item.
- **Sales Order Item.cpq_configuration** (custom field) — links the order
  line back to its configuration snapshot.
- **ss_cpq_pro/api.py** — the entire engine (constraint resolution, pricing,
  order creation) as three whitelisted methods. The Desk Page below is a
  thin client over these — if you ever build a nicer frontend, point it at
  the same three methods and nothing else changes.
- **CPQ Configurator page** (`/app/cpq-configurator`) — the guided UI: pick
  an item, pick a customer, fill in the dynamically-rendered attribute
  fields, watch the price update live, click "Create Sales Order".

## Installation

```bash
# from your bench directory
bench get-app ss_cpq_pro /path/to/ss_cpq_pro   # or your git remote once you push it
bench --site your-site.local install-app ss_cpq_pro
bench --site your-site.local migrate
bench build --app ss_cpq_pro
bench restart
```

`after_install` creates the two custom fields automatically
(`Item.cpq_attribute_group` and `Sales Order Item.cpq_configuration`). If
you're installing on a site that already has the app (re-migrating), those
fields are created with `update=True` so it's safe to re-run.

## Setting up your first configurable product

1. **Create attributes** (`CPQ Attribute` list):
   - `Size` — type Select, values S / M / L / XL, each with a `price_delta`
     if size affects price (usually 0).
   - `Color` — type Select, values Red / Blue / Black.
2. **Create an attribute group** (`CPQ Attribute Group`):
   - Name: "T-Shirt Config"
   - Attributes table: add Size (mandatory) and Color (mandatory).
3. **Link it to an Item**: open the Item, scroll to the new "CPQ" section,
   set CPQ Attribute Group = "T-Shirt Config".
4. **(Optional) Add constraint rules** (`CPQ Constraint Rule`), scoped to
   "T-Shirt Config" — e.g. an Exclusion rule: if Color = Red then Size
   cannot = XL.
5. **Configure it**: open the Item, click **Open CPQ Configurator** (or go
   directly to `/app/cpq-configurator`), pick the item, fill in the fields,
   pick a customer, and click **Create Sales Order**.

## What to check in your dev bench before using this on real data

This was written as a scaffold, not tested against a live bench:

- Run `bench migrate` and open each new doctype in the UI to confirm the
  layout looks right and permissions match your roles (Sales User / Sales
  Manager / System Manager assumptions are in the JSON — adjust as needed).
- Confirm `Item.standard_rate` is the right source for base price in your
  setup — if you use Price Lists instead, swap the lookup in
  `api.get_configurator_data` for `frappe.get_all("Item Price", ...)` or
  `erpnext.stock.get_item_details`.
- The Sales Order created is a **new** Sales Order per configuration. If you
  want the configurator to append a line to an existing draft Sales Order
  instead, that's a small change to `create_sales_order_from_configuration`
  (look up an existing draft SO for the customer before creating a new one).
- Test the constraint rule operators (`>`, `>=`, etc.) with a Number
  attribute end to end — that's the piece most likely to need a tweak for
  your actual data types.

## Phase 2 (not built yet)

`CPQ Configuration` already stores exactly what was selected. Phase 2 would
add a `CPQ BOM Rule` doctype (attribute/value → component + qty formula,
mirroring the Component Mapping table from the discovery exercise) and a
method that resolves an `mrp.bom`-equivalent (ERPNext `BOM` doc) from a
`CPQ Configuration` at Sales Order submission, tied into the MTO route.
