// Copyright (c) 2026, TNL and contributors
// For license information, please see license.txt

const PROPOSAL_SECTION_FIELDS = [
	"executive_summary",
	"technical_approach",
	"commercial_terms",
	"compliance_statement",
];

frappe.ui.form.on("Proposal", {
	refresh(frm) {
		apply_template_sections(frm);
		add_pull_button(frm);
	},
	proposal_template(frm) {
		apply_template_sections(frm);
	},
});

function add_pull_button(frm) {
	// Visibility here is just a convenience — frm.perm reflects doctype-level
	// write, which Business Development/Sales also have; the real Bid
	// Manager-only restriction is enforced server-side in pull_workstream_outputs.
	if (frm.is_new() || !frm.doc.bid || !frm.perm[0].write) return;

	frm.add_custom_button(__("Pull from Workstream Outputs"), () => {
		frm.call("pull_workstream_outputs").then((r) => {
			if (!r.message) return;
			const { pulled, skipped_not_ready } = r.message;
			frm.reload_doc();

			if (pulled.length) {
				frappe.show_alert({ message: __("Pulled: {0}", [pulled.join(", ")]), indicator: "green" });
			}
			if (skipped_not_ready.length) {
				frappe.show_alert({
					message: __("Not yet ready for proposal: {0}", [skipped_not_ready.join(", ")]),
					indicator: "orange",
				});
			}
			if (!pulled.length && !skipped_not_ready.length) {
				frappe.show_alert({ message: __("Nothing to pull — all sections already have content."), indicator: "orange" });
			}
		});
	});
}

function apply_template_sections(frm) {
	if (!frm.doc.proposal_template) {
		PROPOSAL_SECTION_FIELDS.forEach((fieldname) => frm.set_df_property(fieldname, "hidden", 0));
		frm.refresh_fields();
		return;
	}

	frappe.db.get_doc("Proposal Template", frm.doc.proposal_template).then((template) => {
		const included = {};
		(template.sections || []).forEach((row) => {
			included[row.section_key] = !!row.is_included;
		});

		// A template that doesn't list a section at all hides it, same
		// as one that lists it with "Included" unticked.
		PROPOSAL_SECTION_FIELDS.forEach((fieldname) => {
			frm.set_df_property(fieldname, "hidden", !included[fieldname]);
		});
		frm.refresh_fields();

		// Frappe auto-fills any field literally named "letter_head" from a
		// site-wide sticky default the moment the form loads, so an
		// emptiness check here would never actually catch anything — the
		// template's own default has to win outright. Still just a
		// default: the field stays editable afterward for a manual override.
		if (template.default_letter_head) {
			frm.set_value("letter_head", template.default_letter_head);
		}
	});
}
