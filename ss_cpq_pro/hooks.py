from . import __version__ as app_version

app_name = "ss_cpq_pro"
app_title = "SS CPQ Pro"
app_publisher = "Your Company"
app_description = "Lightweight Configure-Price-Quote (CPQ) for ERPNext — sales-side configurator, Phase 1"
app_email = "you@example.com"
app_license = "MIT"

# Runs once when the app is installed on a site.
# Creates the custom fields this app needs on Item and Sales Order Item.
after_install = "ss_cpq_pro.install.after_install"

# App-level bundle entry points (required by Frappe's esbuild asset builder;
# see public/js/ss_cpq_pro.bundle.js for why these exist even though empty)
app_include_js = "/assets/ss_cpq_pro/js/ss_cpq_pro.bundle.js"
app_include_css = "/assets/ss_cpq_pro/css/ss_cpq_pro.bundle.css"

# Attach client script to the Item form (adds the "Open CPQ Configurator" button)
doctype_js = {
	"Item": "public/js/item.js"
}
