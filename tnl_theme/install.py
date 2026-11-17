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
	retire_legacy_crm_workspace()
	retire_legacy_crm_home_card()
	repoint_crm_desktop_layouts()


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


def retire_legacy_crm_workspace():
	"""Delete ERPNext's built-in CRM workspace and repoint its "CRM"
	Desktop Icon (the tile on the /desk home page — a third, separate
	navigation surface from the sidebar, with its own doctype and its own
	stale link) at Frappe CRM, so nothing CRM-like keeps pointing at
	ERPNext's Lead/Opportunity/Customer system once Frappe CRM is
	installed. This only changes dashboard/sidebar/tile pages — the
	underlying doctypes and their data are untouched.

	The Desktop Icon is repointed rather than deleted: deleting it left
	the home screen with no CRM tile at all (see
	_point_crm_desktop_icon_at_frappe_crm).

	Frappe CRM's own workspace is left under its original name ("Frappe
	CRM"), not renamed to plain "CRM". A plain rename was tried first,
	but ERPNext's CRM *module* (distinct from its workspace, which this
	function does remove) is permanently named "CRM" too — and gets
	rebuilt fresh on every page load via frappe.boot.get_sidebar_items()
	-> auto_generate_sidebar_from_module(), which groups doctypes by
	their `module` field from live metadata, not from any stored,
	deletable record. Campaign, Opportunity, etc. will keep declaring
	module="CRM" for as long as ERPNext itself is installed, so that
	fallback sidebar — carrying the exact same "Home" link to a Dashboard
	named "CRM" that caused /desk/dashboard-view/CRM in the first place —
	regenerates no matter what Workspace/Workspace Sidebar records get
	deleted or renamed. "CRM" as an exact name is a permanent collision
	with that module, not a fixable bug; "Frappe CRM" avoids it entirely.

	Also cleans up after that earlier rename attempt: undoes it if still
	in place.

	Guarded by exists() checks since a site without Frappe CRM installed
	shouldn't error, and re-applied on every migrate so it also reaches
	sites that already existed before this fixup was added."""
	if frappe.db.exists("Workspace", "CRM"):
		if frappe.db.get_value("Workspace", "CRM", "module") == "FCRM":
			frappe.rename_doc("Workspace", "CRM", "Frappe CRM", force=True, show_alert=False)
			frappe.db.set_value("Workspace", "Frappe CRM", "label", "Frappe CRM")
			frappe.db.set_value("Workspace", "Frappe CRM", "title", "Frappe CRM")
			frappe.clear_document_cache("Workspace", "Frappe CRM")
		else:
			frappe.delete_doc("Workspace", "CRM", ignore_permissions=True, force=True)

	_point_crm_desktop_icon_at_frappe_crm()

	# Deliberately unconditional: Desktop Icon.on_trash() only clears
	# clear_desktop_icons_cache() for frappe.session.user — whoever's
	# session is running the delete (Administrator, during migrate) —
	# not for every user who already had their own icons cached, so each
	# real user keeps their own stale "desktop_icons" hash entry
	# regardless of whether this specific run is the one that deleted
	# the record. Standard icons are meant to invalidate for everyone at
	# once — see Desktop Icon.on_update()'s own `if self.standard`
	# branch, which clears this same full key rather than one user's
	# entry — so this has to run every time this function runs, the same
	# way the bootinfo clear below already does, not just the one run
	# where the record happened to still exist to delete.
	frappe.cache.delete_key("desktop_icons")

	_rebuild_frappe_crm_sidebar()

	# Public workspaces (for_user is blank) fall into the branch of
	# Workspace.clear_cache() that clears the shared "bootinfo" cache key
	# rather than a specific user's — Desk's sidebar is built from
	# bootinfo, so without this the old values keep appearing at login
	# even after the DB itself is correct.
	frappe.cache.delete_key("bootinfo")


def retire_legacy_crm_home_card():
	"""Remove the stock "CRM" card ERPNext seeds onto the Home workspace's
	own "Reports & Masters" section (Lead / Customer Group / Territory on
	a fresh install) — a fourth, independent place old CRM doctypes were
	still one click away, on top of the workspace/sidebar/desktop-icon
	trio retire_legacy_crm_workspace already handles. Home is generic
	ERPNext furniture, not something either app manages, so this edits it
	directly rather than via a fixture.

	Removes the "CRM" Card Break row and every Link row that follows it
	up to the next Card Break, plus the matching {"type": "card", "data":
	{"card_name": "CRM"}} block in `content` — the two are separate,
	parallel representations of the same page, and both have to change
	or the card renders empty instead of disappearing.

	Idempotent — a no-op once the card is gone — and re-applied on every
	migrate the same way as retire_legacy_crm_workspace."""
	if not frappe.db.exists("Workspace", "Home"):
		return

	home = frappe.get_doc("Workspace", "Home")

	start = next(
		(i for i, row in enumerate(home.links) if row.type == "Card Break" and row.label == "CRM"),
		None,
	)
	if start is None:
		return

	end = next(
		(i for i, row in enumerate(home.links) if i > start and row.type == "Card Break"),
		len(home.links),
	)
	del home.links[start:end]
	for i, row in enumerate(home.links):
		row.idx = i + 1

	import json

	blocks = json.loads(home.content)
	blocks = [
		block
		for block in blocks
		if not (block.get("type") == "card" and block.get("data", {}).get("card_name") == "CRM")
	]
	home.content = json.dumps(blocks, separators=(",", ":"))

	home.save(ignore_permissions=True)
	frappe.cache.delete_key("bootinfo")


def _point_crm_desktop_icon_at_frappe_crm():
	"""Make the "CRM" home-screen tile open Frappe CRM (/crm).

	ERPNext ships a standard "CRM" Desktop Icon (erpnext/desktop_icon/
	crm.json) linked to its CRM Workspace Sidebar, whose first link is
	Campaign — that's what sent the tile to /desk/campaign. It used to be
	deleted here instead, but that left no CRM tile at all: Frappe CRM's
	own app icon isn't on the home screen. So the record is kept and
	repointed in place as an External link to /crm, shown at the top
	level instead of inside the ERPNext folder.

	Created when missing, since ERPNext's sync only re-adds it on the
	next migrate. Written with db.set_value so ERPNext's sync of
	crm.json (which runs before after_migrate) is simply overridden again
	on every migrate."""
	values = {
		"icon_type": "Link",
		"link_type": "External",
		"link": "/crm",
		"link_to": None,
		"hidden": 0,
		"parent_icon": None,
	}
	if frappe.db.exists("Desktop Icon", "CRM"):
		frappe.db.set_value("Desktop Icon", "CRM", values)
	else:
		frappe.get_doc(
			{"doctype": "Desktop Icon", "label": "CRM", "icon": "handshake", "standard": 1, **values}
		).insert(ignore_permissions=True)


def repoint_crm_desktop_layouts():
	"""Point the "CRM" tile in every user's saved Desktop Layout at
	Frappe CRM (/crm) instead of ERPNext's old CRM sidebar.

	A Desktop Layout is a per-user, frozen JSON snapshot of every icon
	(label, link_type, link...) taken the first time that user edits or
	rearranges their /desk home screen. Once one exists, desktop.js
	renders straight from it (DesktopPage.sync_layout ->
	frappe.desktop_icons = this.data) and never looks at the Desktop
	Icon table again — so deleting the "CRM" Desktop Icon in
	retire_legacy_crm_workspace didn't reach these users at all. Their
	snapshot still carries the old {"label": "CRM", "link_type":
	"Workspace Sidebar"} entry, which get_route() resolves through
	frappe.boot.workspace_sidebar_item["crm"] — ERPNext's CRM-module
	fallback sidebar, which can never be removed (see
	retire_legacy_crm_workspace) and whose first link is Campaign,
	hence /desk/campaign.

	Rewrites that entry into an External link to /crm rather than
	dropping it, so users keep the tile where they placed it. Icons can
	be nested under a folder's `child_icons`, so the walk is recursive.

	Idempotent — External entries are skipped — and re-applied on every
	migrate, since any user can still be holding an older snapshot."""
	def repoint(icons):
		changed = False
		for icon in icons:
			if not isinstance(icon, dict):
				continue
			if icon.get("label") == "CRM" and icon.get("link_type") != "External":
				icon["link_type"] = "External"
				icon["link"] = "/crm"
				icon["link_to"] = None
				changed = True
			if repoint(icon.get("child_icons") or []):
				changed = True
		return changed

	import json

	for name, layout in frappe.get_all("Desktop Layout", fields=["name", "layout"], as_list=True):
		try:
			icons = json.loads(layout or "[]")
		except ValueError:
			continue
		if isinstance(icons, list) and repoint(icons):
			frappe.db.set_value("Desktop Layout", name, "layout", json.dumps(icons))


def _rebuild_frappe_crm_sidebar():
	"""Give Frappe CRM's workspace its own explicit "Workspace Sidebar",
	rebuilt fresh on every migrate.

	Without this, Desk falls back to auto-generating one from module
	membership (frappe.desk.doctype.workspace_sidebar.workspace_sidebar.
	auto_generate_sidebar_from_module) — but that fallback is keyed by
	*module* name ("fcrm", lowercased) while the frontend looks the
	sidebar up by the *workspace's* title ("frappe crm", lowercased,
	from frappe.ui.sidebar.sidebar_item.js). Those only match when a
	workspace happens to be named exactly like its own module, which
	isn't true here (workspace "Frappe CRM", module "FCRM") — so the
	lookup silently misses and some unrelated sidebar item (observed:
	ERPNext's own "CRM"-module fallback, landing on /desk/campaign)
	ends up shown instead.

	Reuses auto_generate_sidebar_from_module()'s own item-building logic
	(it already produces a correct, unsaved "Workspace Sidebar" doc for
	the FCRM module) and just fixes the one thing wrong with it: stores
	it under the workspace's real title instead of the module name, so
	the frontend's lookup actually finds it.

	Has to re-run every migrate, not just once: this doctype has no
	on-disk fixture in any app, so migrate's orphan-cleanup deletes
	whatever's here on every single run regardless of what it's named.

	Newer Frappe v16 releases removed auto_generate_sidebar_from_module.
	When it's gone this skips the rebuild rather than raising, because an
	exception here aborts the whole `bench migrate` — including every
	after_migrate hook queued after this one."""
	try:
		from frappe.desk.doctype.workspace_sidebar.workspace_sidebar import (
			auto_generate_sidebar_from_module,
		)
	except ImportError:
		return

	for sidebar_name in ("CRM", "Frappe CRM"):
		if frappe.db.exists("Workspace Sidebar", sidebar_name):
			frappe.delete_doc("Workspace Sidebar", sidebar_name, ignore_permissions=True, force=True)

	if not frappe.db.exists("Workspace", "Frappe CRM"):
		return

	fcrm_sidebar = next(
		(s for s in auto_generate_sidebar_from_module() if s.module == "FCRM"), None
	)
	if fcrm_sidebar:
		fcrm_sidebar.title = "Frappe CRM"
		fcrm_sidebar.insert(ignore_permissions=True)
