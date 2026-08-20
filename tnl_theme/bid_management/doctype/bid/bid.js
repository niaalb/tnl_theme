// Copyright (c) 2026, TNL and contributors
// For license information, please see license.txt

const BID_STAGES = ["Identified", "Handed Off", "Qualifying", "Kickoff", "In Progress", "Submitted", "Closed"];

const STAGE_COLORS = {
	Identified: "#8d99a6",
	"Handed Off": "#f39c12",
	Qualifying: "#f1c40f",
	Kickoff: "#3498db",
	"In Progress": "#3498db",
	Submitted: "#9b59b6",
	Closed: "#2ecc71",
};

frappe.ui.form.on("Bid", {
	refresh(frm) {
		render_stage_tracker(frm);
		render_workstream_progress(frm);
		render_escalation_banner(frm);
		set_page_indicator(frm);
	},
});

function set_page_indicator(frm) {
	if (frm.doc.stage === "Closed") {
		if (frm.doc.outcome === "Won") {
			frm.page.set_indicator(__("Won"), "green");
		} else if (frm.doc.outcome === "Lost") {
			frm.page.set_indicator(__("Lost"), "red");
		} else {
			frm.page.set_indicator(__("Closed"), "gray");
		}
		return;
	}
	frm.page.set_indicator(__(frm.doc.stage), "blue");
}

function render_stage_tracker(frm) {
	const current_idx = BID_STAGES.indexOf(frm.doc.stage);

	const steps = BID_STAGES.map((stage, idx) => {
		const done = idx < current_idx;
		const active = idx === current_idx;
		const color = done || active ? STAGE_COLORS[stage] : "var(--gray-300)";
		const label_color = done || active ? "var(--text-color)" : "var(--text-muted)";

		return `
			<div class="bid-step" style="display:flex;flex-direction:column;align-items:center;flex:1;min-width:0;">
				<div style="
					width: ${active ? "16px" : "12px"};
					height: ${active ? "16px" : "12px"};
					border-radius: 50%;
					background: ${color};
					box-shadow: ${active ? `0 0 0 4px ${color}33` : "none"};
					margin-bottom: 6px;
				"></div>
				<div style="font-size:11px;text-align:center;color:${label_color};font-weight:${active ? "600" : "400"};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:90px;">
					${__(stage)}
				</div>
			</div>`;
	}).join(`<div class="bid-step-line" style="flex:0 0 auto;height:2px;width:24px;background:var(--gray-300);margin:5px -2px 0;"></div>`);

	const html = `<div style="display:flex;align-items:flex-start;padding:8px 4px 4px;overflow-x:auto;">${steps}</div>`;

	if (!frm.__bid_stage_section) {
		frm.__bid_stage_section = frm.dashboard.add_section(html, __("Bid Pipeline"));
	} else {
		frm.__bid_stage_section.html(html);
	}
}

function render_workstream_progress(frm) {
	const statuses = [frm.doc.technical_status, frm.doc.financial_status, frm.doc.administrative_status];
	const completed = statuses.filter((s) => s === "Completed").length;
	const blocked = statuses.some((s) => s === "Blocked");
	const percent = Math.round((completed / 3) * 100);

	if (!frm.doc.technical_lead && !frm.doc.financial_lead && !frm.doc.administrative_lead) {
		return;
	}

	const message = blocked
		? __("One or more workstreams are blocked")
		: __("{0} of 3 workstreams completed", [completed]);

	frm.dashboard.add_progress(__("Workstream Progress"), blocked ? -1 : percent, message);
}

function render_escalation_banner(frm) {
	const escalations = [];
	if (frm.doc.handoff_escalated) escalations.push(__("hand-off acknowledgment"));
	if (frm.doc.escalated_technical) escalations.push(__("Technical checkpoint"));
	if (frm.doc.escalated_financial) escalations.push(__("Financial checkpoint"));
	if (frm.doc.escalated_administrative) escalations.push(__("Administrative checkpoint"));

	if (escalations.length) {
		frm.dashboard.set_headline_alert(
			`<i class="fa fa-exclamation-triangle"></i> ${__("Escalated: {0} overdue", [escalations.join(", ")])}`,
			"red",
			true
		);
	}
}
