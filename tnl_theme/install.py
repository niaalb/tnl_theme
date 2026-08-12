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

	hide_frappe_help_links()


def hide_frappe_help_links():
	"""Hide every stock Help-menu link that points at Frappe's own docs/
	community/support pages — they leak the fact that this is a themed
	Frappe install rather than a bespoke product, undercutting the
	branding work everywhere else. Uses each item's own `hidden` flag
	rather than a CSS hide, since Navbar Settings is a real, supported
	extension point for this. "Keyboard Shortcuts" is the one item kept,
	since it's generically useful and carries no Frappe branding."""
	links_to_hide = {
		"https://docs.erpnext.com/",
		"https://discuss.frappe.io",
		"https://frappe.io/school?utm_source=in_app",
		"https://github.com/frappe/erpnext/issues",
		"frappe.ui.toolbar.show_about()",
		"/desk/system-health-report",
		"https://frappe.io/support",
	}
	navbar_settings = frappe.get_single("Navbar Settings")
	changed = False
	for item in navbar_settings.help_dropdown:
		if (item.action or item.route) in links_to_hide and not item.hidden:
			item.hidden = 1
			changed = True
	if changed:
		navbar_settings.save(ignore_permissions=True)
