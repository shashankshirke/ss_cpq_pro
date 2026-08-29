import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
	create_cpq_custom_fields()


def create_cpq_custom_fields():
	"""
	Adds the two touch points this app needs on core doctypes:
	- Item.cpq_attribute_group: tells the configurator which attributes to render for this item
	- Sales Order Item.cpq_configuration: links the order line back to the exact configuration
	  that was used to build it, for traceability and (later) BOM generation in Phase 2.
	"""
	custom_fields = {
		"Item": [
			{
				"fieldname": "cpq_section_break",
				"label": "CPQ",
				"fieldtype": "Section Break",
				"insert_after": "item_group",
				"collapsible": 1,
			},
			{
				"fieldname": "cpq_attribute_group",
				"label": "CPQ Attribute Group",
				"fieldtype": "Link",
				"options": "CPQ Attribute Group",
				"insert_after": "cpq_section_break",
				"description": "If set, this item can be configured through the CPQ Configurator.",
			},
		],
		"Sales Order Item": [
			{
				"fieldname": "cpq_configuration",
				"label": "CPQ Configuration",
				"fieldtype": "Link",
				"options": "CPQ Configuration",
				"insert_after": "item_code",
				"read_only": 1,
				"allow_on_submit": 1,
			},
		],
	}
	create_custom_fields(custom_fields, update=True)
