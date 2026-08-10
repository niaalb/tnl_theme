// Brand override for the sidebar's workspace-switcher header icon.
//
// That icon is rendered by Frappe as either a plain <img src="..."> (when a
// matching desktop-icon file is registered in frappe.boot.desktop_icon_urls)
// or a generated single-letter avatar (when it isn't) — confirmed by
// inspecting the live page that the same workspace can hit either path.
// Neither case is reliably selectable by CSS alone (the letter-avatar has no
// per-workspace attribute to key off), so this reapplies our own icon
// directly whenever the header re-renders, keyed off the workspace title
// text, which is always present.
(function () {
	const ICON_BY_WORKSPACE = {
		Organization: "/assets/tnl_theme/images/icons/organization.png",
		CRM: "/assets/tnl_theme/images/icons/crm.png",
		Projects: "/assets/tnl_theme/images/icons/projects.png",
		Raven: "/assets/tnl_theme/images/icons/raven.png",
		Invoicing: "/assets/tnl_theme/images/icons/accounting/invoicing.svg",
		"Financial Reports": "/assets/tnl_theme/images/icons/accounting/financial_reports.svg",
		"ERPNext Settings": "/assets/tnl_theme/images/icons/erpnext_settings.svg",
	};

	function apply_custom_header_icon() {
		const header = document.querySelector(".sidebar-header");
		if (!header) return;

		const title_el = header.querySelector(".header-title");
		const logo_el = header.querySelector(".header-logo");
		if (!title_el || !logo_el) return;

		const title = title_el.textContent.trim();
		const icon_url = ICON_BY_WORKSPACE[title];
		if (!icon_url || logo_el.dataset.tnlIcon === icon_url) return;

		logo_el.innerHTML = `<img src="${icon_url}" style="width: 100%; height: 100%; object-fit: contain;">`;
		logo_el.dataset.tnlIcon = icon_url;
	}

	frappe.after_ajax(() => {
		const sidebar = document.querySelector(".body-sidebar") || document.body;
		new MutationObserver(apply_custom_header_icon).observe(sidebar, {
			childList: true,
			subtree: true,
			characterData: true,
		});
		apply_custom_header_icon();
	});
})();
