frappe.pages['cpq-configurator'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('CPQ Configurator'),
		single_column: true,
	});

	new ss_cpq_pro.Configurator(page);
};

frappe.provide('ss_cpq_pro');

ss_cpq_pro.Configurator = class {
	constructor(page) {
		this.page = page;
		this.selections = {};
		this.attribute_fields = {};
		this.make_layout();
		this.bind_events();

		// Allow deep-linking: frappe.set_route('cpq-configurator', {item_code: 'ITEM-001'})
		const item_code = frappe.route_options && frappe.route_options.item_code;
		if (item_code) {
			frappe.route_options = null;
			this.item_field.set_value(item_code);
		}
	}

	make_layout() {
		this.$body = $(`
			<div class="cpq-configurator">
				<div class="row">
					<div class="col-sm-4">
						<div class="cpq-setup"></div>
						<div class="cpq-attributes" style="margin-top: 20px;"></div>
					</div>
					<div class="col-sm-4">
						<div class="cpq-summary"></div>
					</div>
				</div>
			</div>
		`).appendTo(this.page.body);

		this.setup_wrapper = this.$body.find('.cpq-setup');
		this.attributes_wrapper = this.$body.find('.cpq-attributes');
		this.summary_wrapper = this.$body.find('.cpq-summary');

		this.item_field = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Link',
				options: 'Item',
				fieldname: 'item_code',
				label: __('Item'),
				reqd: 1,
				get_query: () => ({ filters: { disabled: 0 } }),
			},
			parent: this.setup_wrapper,
			render_input: true,
		});

		this.customer_field = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Link',
				options: 'Customer',
				fieldname: 'customer',
				label: __('Customer'),
				reqd: 1,
			},
			parent: this.setup_wrapper,
			render_input: true,
		});

		this.qty_field = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Float',
				fieldname: 'qty',
				label: __('Quantity'),
				default: 1,
			},
			parent: this.setup_wrapper,
			render_input: true,
		});
		this.qty_field.set_value(1);

		this.render_summary();
	}

	bind_events() {
		this.item_field.df.onchange = () => this.on_item_change();
		this.item_field.refresh();
	}

	on_item_change() {
		const item_code = this.item_field.get_value();
		this.attributes_wrapper.empty();
		this.attribute_fields = {};
		this.selections = {};
		this.config_data = null;
		this.last_result = null;
		this.render_summary();

		if (!item_code) return;

		frappe.call({
			method: 'ss_cpq_pro.api.get_configurator_data',
			args: { item_code },
			freeze: true,
			callback: (r) => {
				if (!r.message) return;
				this.config_data = r.message;
				this.render_attribute_fields();
				this.refresh_price();
			},
		});
	}

	render_attribute_fields() {
		this.config_data.attributes.forEach((attr) => {
			let df;
			if (attr.attribute_type === 'Select') {
				df = {
					fieldtype: 'Select',
					fieldname: attr.attribute,
					label: attr.attribute,
					reqd: attr.is_mandatory,
					options: ['', ...attr.values.map((v) => v.value)].join('\n'),
				};
			} else if (attr.attribute_type === 'Number') {
				df = {
					fieldtype: 'Float',
					fieldname: attr.attribute,
					label: attr.attribute,
					reqd: attr.is_mandatory,
					description:
						attr.min_value || attr.max_value
							? __('Range: {0} – {1}', [attr.min_value || 0, attr.max_value || '∞'])
							: '',
				};
			} else {
				df = {
					fieldtype: 'Data',
					fieldname: attr.attribute,
					label: attr.attribute,
					reqd: attr.is_mandatory,
				};
			}

			const field = frappe.ui.form.make_control({
				df,
				parent: this.attributes_wrapper,
				render_input: true,
			});

			if (attr.default_value) {
				field.set_value(attr.default_value);
				this.selections[attr.attribute] = attr.default_value;
			}

			field.df.onchange = () => {
				this.selections[attr.attribute] = field.get_value();
				this.refresh_price();
			};
			field.refresh();

			this.attribute_fields[attr.attribute] = field;
		});
	}

	refresh_price() {
		const item_code = this.item_field.get_value();
		if (!item_code) return;

		frappe.call({
			method: 'ss_cpq_pro.api.validate_and_price_configuration',
			args: { item_code, selections: this.selections },
			callback: (r) => {
				if (!r.message) return;
				this.last_result = r.message;

				// reflect any auto-derived values back into their fields
				// (e.g. Trim=Performance forces Drivetrain=AWD)
				Object.entries(r.message.derived || {}).forEach(([attribute, value]) => {
					const field = this.attribute_fields[attribute];
					if (field && field.get_value() !== value) {
						field.set_value(value);
					}
					this.selections[attribute] = value;
				});

				this.render_summary();
			},
		});
	}

	render_summary() {
		const result = this.last_result;
		let html = '<div class="cpq-summary-card" style="border: 1px solid var(--border-color); border-radius: 8px; padding: 16px;">';
		html += `<h5>${__('Price Summary')}</h5>`;

		if (!result) {
			html += `<p class="text-muted">${__('Select an item to begin')}</p>`;
		} else {
			html += '<table class="table table-condensed">';
			html += `<tr><td>${__('Base price')}</td><td class="text-right">${format_currency(result.base_price)}</td></tr>`;
			(result.price_breakdown || []).forEach((row) => {
				html += `<tr><td>${frappe.utils.escape_html(row.attribute)}: ${frappe.utils.escape_html(String(row.value))}</td><td class="text-right">${format_currency(row.price_delta)}</td></tr>`;
			});
			html += `<tr><th>${__('Total')}</th><th class="text-right">${format_currency(result.total_price)}</th></tr>`;
			html += '</table>';

			if (result.errors && result.errors.length) {
				html += '<div class="text-danger" style="margin-top: 10px;">';
				result.errors.forEach((e) => (html += `<div>${e}</div>`));
				html += '</div>';
			}
		}
		html += '</div>';

		this.summary_wrapper.html(html);

		this.summary_wrapper.find('.btn-cpq-create').remove();
		if (result && result.valid) {
			$(`<button class="btn btn-primary btn-sm btn-cpq-create" style="margin-top: 12px;">
				${__('Create Sales Order')}
			</button>`)
				.appendTo(this.summary_wrapper)
				.on('click', () => this.create_sales_order());
		}
	}

	create_sales_order() {
		const item_code = this.item_field.get_value();
		const customer = this.customer_field.get_value();
		const qty = this.qty_field.get_value() || 1;

		if (!customer) {
			frappe.msgprint(__('Please select a Customer'));
			return;
		}

		frappe.call({
			method: 'ss_cpq_pro.api.create_sales_order_from_configuration',
			args: { item_code, customer, selections: this.selections, qty },
			freeze: true,
			callback: (r) => {
				if (!r.message) return;
				frappe.show_alert({
					message: __('Sales Order {0} created', [r.message.sales_order]),
					indicator: 'green',
				});
				frappe.set_route('Form', 'Sales Order', r.message.sales_order);
			},
		});
	}
};
