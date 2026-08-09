import frappe


def after_install():
	"""Point Website Settings at the logo assets bundled with this app, so
	branding is live immediately on install instead of requiring a manual
	upload on every new site.

	Two variants are shipped: the wide logotype for the navbar/login (where
	there's room for the full mark), and a square icon-only crop for favicon
	and splash (a wide banner would get squished into a tiny tab icon)."""
	logo = "/assets/tnl_theme/images/logo.png"
	icon = "/assets/tnl_theme/images/icon.png"
	settings = frappe.get_single("Website Settings")
	settings.app_logo = logo
	settings.favicon = icon
	settings.splash_image = icon
	settings.save(ignore_permissions=True)
