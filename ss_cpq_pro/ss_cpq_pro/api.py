"""
SS CPQ Pro — Phase 1 (sales-side only) API.

Everything the configurator UI needs lives here as whitelisted methods.
This is deliberate: the UI (currently a Desk Page) is a thin client over
this module, so a future Frappe UI / portal frontend can call the exact
same three methods without any backend changes.

Resolution pipeline (matches the discovery method used to design the
attribute/constraint/pricing tables):
    1. get_configurator_data      -> what can be selected, and the rules
    2. validate_and_price_configuration -> constraints first, then price
    3. create_sales_order_from_configuration -> snapshot + Sales Order
"""

import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_configurator_data(item_code):
	"""Return the attribute group, ordered attributes (with values), active
	constraint rules, and base price for the given item."""
	item = frappe.db.get_value(
		"Item", item_code, ["cpq_attribute_group", "standard_rate"], as_dict=True
	)
	if not item:
		frappe.throw(_("Item {0} not found").format(item_code))
	if not item.cpq_attribute_group:
		frappe.throw(_("Item {0} does not have a CPQ Attribute Group set").format(item_code))

	group = frappe.get_doc("CPQ Attribute Group", item.cpq_attribute_group)

	attributes = []
	for row in sorted(group.attributes, key=lambda r: (r.sequence or 0)):
		attr = frappe.get_doc("CPQ Attribute", row.attribute)
		attributes.append(
			{
				"attribute": attr.name,
				"attribute_type": attr.attribute_type,
				"is_mandatory": row.is_mandatory,
				"default_value": row.default_value_override or attr.default_value,
				"min_value": attr.min_value,
				"max_value": attr.max_value,
				"price_per_unit": attr.price_per_unit,
				"values": (
					[
						{
							"value": v.value,
							"price_delta": v.price_delta,
							"is_default": v.is_default,
						}
						for v in sorted(attr.values, key=lambda v: (v.sequence or 0))
					]
					if attr.attribute_type == "Select"
					else []
				),
			}
		)

	rules = frappe.get_all(
		"CPQ Constraint Rule",
		filters={"attribute_group": group.name, "is_active": 1},
		fields=["rule_type", "if_attribute", "if_operator", "if_value", "then_attribute", "then_value"],
	)

	return {
		"attribute_group": group.name,
		"attributes": attributes,
		"rules": rules,
		"base_price": flt(item.standard_rate),
	}


def _compare(value, operator, target):
	"""Evaluate `value <operator> target`. `=` and `!=` work on strings
	(covers Select/Text attributes); the rest require numeric values
	(covers Number attributes, e.g. Length > 2000)."""
	if operator == "=":
		return str(value) == str(target)
	if operator == "!=":
		return str(value) != str(target)

	try:
		value_f, target_f = flt(value), flt(target)
	except (TypeError, ValueError):
		frappe.throw(_("Operator {0} requires a numeric value").format(operator))

	if operator == ">":
		return value_f > target_f
	if operator == ">=":
		return value_f >= target_f
	if operator == "<":
		return value_f < target_f
	if operator == "<=":
		return value_f <= target_f
	frappe.throw(_("Unknown operator {0}").format(operator))


@frappe.whitelist()
def validate_and_price_configuration(item_code, selections):
	"""
	selections: dict of {attribute_name: value}

	Runs the same pipeline every time, in this order:
	  1. mandatory-field check
	  2. constraint rules (Mandatory rules auto-derive a value; Exclusion
	     rules reject an incompatible combination)
	  3. pricing (base price + per-attribute deltas / formulas)

	Returns a dict the UI can render directly: errors, any auto-derived
	values, a price breakdown, and the total.
	"""
	if isinstance(selections, str):
		selections = frappe.parse_json(selections)
	selections = dict(selections or {})

	data = get_configurator_data(item_code)
	attributes_by_name = {a["attribute"]: a for a in data["attributes"]}

	errors = []
	derived = {}

	# 1. mandatory check (skip attributes a rule is about to derive)
	rule_targets = {r["then_attribute"] for r in data["rules"] if r["rule_type"] == "Mandatory"}
	for attr in data["attributes"]:
		if (
			attr["is_mandatory"]
			and not selections.get(attr["attribute"])
			and attr["attribute"] not in rule_targets
		):
			errors.append(_("{0} is required").format(attr["attribute"]))

	# 2. constraint rules
	for rule in data["rules"]:
		if_value = selections.get(rule["if_attribute"])
		if if_value in (None, ""):
			continue
		if not _compare(if_value, rule["if_operator"], rule["if_value"]):
			continue

		if rule["rule_type"] == "Mandatory":
			current = selections.get(rule["then_attribute"])
			if current and str(current) != str(rule["then_value"]):
				errors.append(
					_("Since {0} = {1}, {2} must be {3}").format(
						rule["if_attribute"], if_value, rule["then_attribute"], rule["then_value"]
					)
				)
			else:
				derived[rule["then_attribute"]] = rule["then_value"]
				selections[rule["then_attribute"]] = rule["then_value"]
		elif rule["rule_type"] == "Exclusion":
			current = selections.get(rule["then_attribute"])
			if current and str(current) == str(rule["then_value"]):
				errors.append(
					_("{0} cannot be {1} when {2} = {3}").format(
						rule["then_attribute"], rule["then_value"], rule["if_attribute"], if_value
					)
				)

	# 3. pricing
	price_breakdown = []
	total = flt(data["base_price"])

	for attr_name, value in selections.items():
		attr = attributes_by_name.get(attr_name)
		if not attr or value in (None, ""):
			continue

		delta = 0
		if attr["attribute_type"] == "Select":
			match = next((v for v in attr["values"] if v["value"] == value), None)
			delta = flt(match["price_delta"]) if match else 0
		elif attr["attribute_type"] == "Number":
			delta = flt(value) * flt(attr["price_per_unit"])

		if delta:
			price_breakdown.append({"attribute": attr_name, "value": value, "price_delta": delta})
			total += delta

	return {
		"valid": len(errors) == 0,
		"errors": errors,
		"derived": derived,
		"selections": selections,
		"base_price": data["base_price"],
		"price_breakdown": price_breakdown,
		"total_price": total,
	}


@frappe.whitelist()
def create_sales_order_from_configuration(item_code, customer, selections, qty=1, company=None):
	"""Re-validates the configuration server-side (never trust the client's
	price), then creates a CPQ Configuration snapshot and a Sales Order
	whose line is linked back to it."""
	if isinstance(selections, str):
		selections = frappe.parse_json(selections)

	result = validate_and_price_configuration(item_code, selections)
	if not result["valid"]:
		frappe.throw("<br>".join(result["errors"]))

	qty = flt(qty) or 1
	company = company or frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw(_("No default Company set for your user — pass one explicitly"))

	config = frappe.get_doc(
		{
			"doctype": "CPQ Configuration",
			"item": item_code,
			"customer": customer,
			"qty": qty,
			"base_price": result["base_price"],
			"total_price": result["total_price"],
			"configuration_details": [
				{
					"attribute": row["attribute"],
					"attribute_value": row["value"],
					"price_delta": row["price_delta"],
				}
				for row in result["price_breakdown"]
			],
		}
	)
	config.insert(ignore_permissions=True)

	so = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"customer": customer,
			"company": company,
			"delivery_date": frappe.utils.add_days(frappe.utils.nowdate(), 7),
			"items": [
				{
					"item_code": item_code,
					"qty": qty,
					"rate": result["total_price"],
					"cpq_configuration": config.name,
				}
			],
		}
	)
	so.insert(ignore_permissions=True)

	config.sales_order = so.name
	config.status = "Converted"
	config.save(ignore_permissions=True)

	return {"sales_order": so.name, "configuration": config.name, "total_price": result["total_price"]}
