frappe.ui.form.on('Item', {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.cpq_attribute_group) {
			frm.add_custom_button(__('Open CPQ Configurator'), () => {
				frappe.set_route('cpq-configurator', { item_code: frm.doc.name });
			});
		}
	},
});
