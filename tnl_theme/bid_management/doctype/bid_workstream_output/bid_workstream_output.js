// Copyright (c) 2026, TNL and contributors
// For license information, please see license.txt

const WORKSTREAM_LEAD_FIELD = {
	Technical: "technical_lead",
	Financial: "financial_lead",
	Administrative: "administrative_lead",
};

const WORKSTREAM_STATUS_FIELD = {
	Technical: "technical_status",
	Financial: "financial_status",
	Administrative: "administrative_status",
};

frappe.ui.form.on("Bid Workstream Output", {
	refresh(frm) {
		set_page_title(frm);
		set_ready_indicator(frm);
		render_context_section(frm);
	},
	bid(frm) {
		render_context_section(frm);
	},
	workstream(frm) {
		set_page_title(frm);
		render_context_section(frm);
	},
	ready_for_proposal(frm) {
		set_ready_indicator(frm);
	},
});

function set_page_title(frm) {
	if (frm.doc.workstream && frm.doc.bid) {
		frm.page.set_title(`${__(frm.doc.workstream)} — ${frm.doc.bid}`);
	}
}

function set_ready_indicator(frm) {
	if (frm.is_new()) return;
	if (frm.doc.ready_for_proposal) {
		frm.page.set_indicator(__("Ready for Proposal"), "green");
	} else {
		frm.page.set_indicator(__("Draft"), "orange");
	}
}

function render_context_section(frm) {
	if (!frm.doc.bid || !frm.doc.workstream) return;

	const lead_field = WORKSTREAM_LEAD_FIELD[frm.doc.workstream];
	const status_field = WORKSTREAM_STATUS_FIELD[frm.doc.workstream];

	frappe.db.get_value("Bid", frm.doc.bid, ["client_account", lead_field, status_field]).then(({ message }) => {
		if (!message) return;

		const lead_user = message[lead_field];
		const lead = lead_user ? frappe.user_info(lead_user).fullname : __("Not yet assigned");
		const status = __(message[status_field] || "Not Started");
		const word_count = get_word_count(frm.doc.content);

		const html = `
			<div style="display: flex; flex-wrap: wrap; gap: 4px 28px; font-size: var(--text-sm);">
				<div><span class="text-muted">${__("Bid")}:</span>
					<a href="/app/bid/${encodeURIComponent(frm.doc.bid)}">
						${frappe.utils.escape_html(message.client_account || frm.doc.bid)}
					</a>
				</div>
				<div><span class="text-muted">${__("Workstream")}:</span> ${__(frm.doc.workstream)}</div>
				<div><span class="text-muted">${__("Lead")}:</span> ${frappe.utils.escape_html(lead)}</div>
				<div><span class="text-muted">${__("Workstream Status")}:</span> ${status}</div>
				${word_count ? `<div class="text-muted">${__("{0} words", [word_count])}</div>` : ""}
			</div>`;

		if (!frm.__bwo_context_section) {
			frm.__bwo_context_section = frm.dashboard.add_section(html, __("Preparing For"));
		} else {
			frm.__bwo_context_section.html(html);
		}
	});
}

function get_word_count(html) {
	if (!html) return 0;
	const text = $("<div>").html(html).text().trim();
	return text ? text.split(/\s+/).length : 0;
}
