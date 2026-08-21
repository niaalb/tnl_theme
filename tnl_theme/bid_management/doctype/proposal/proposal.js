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
	},
	proposal_template(frm) {
		apply_template_sections(frm);
	},
});

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
