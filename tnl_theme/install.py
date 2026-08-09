import frappe


def after_install():
	"""Point Website Settings at the logo bundled with this app, so branding
	is live immediately on install instead of requiring a manual upload on
	every new site."""
	logo = "/assets/tnl_theme/images/logo.png"
	settings = frappe.get_single("Website Settings")
	settings.app_logo = logo
	settings.favicon = logo
	settings.splash_image = logo
	settings.save(ignore_permissions=True)
