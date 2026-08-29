import frappe
from frappe import _
from frappe.model.document import Document


class CPQAttribute(Document):
	def validate(self):
		if self.attribute_type == "Select" and not self.values:
			frappe.throw(_("Add at least one value for a Select-type attribute"))
