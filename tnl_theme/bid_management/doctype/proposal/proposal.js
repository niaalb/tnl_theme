// Copyright (c) 2026, TNL and contributors
// For license information, please see license.txt

const PROPOSAL_SECTION_FIELDS = [
	"executive_summary",
	"technical_approach",
	"commercial_terms",
	"compliance_statement",
];

const STATUS_COLORS = {
	Draft: "orange",
	Final: "blue",
	Sent: "green",
	Superseded: "gray",
};

const SIGNATURE_STATUS_COLORS = {
	Sent: "blue",
	Signed: "green",
	Declined: "red",
};

// Matches proposal.py's own SIGNATURE_FIELD_TYPES-equivalent (the Select
// options on Proposal Signature Field) — a fraction of whichever page a
// box starts on, just to give a sensible first position before the user
// drags it wherever it actually belongs.
const SIGNATURE_FIELD_TYPES = ["Signature", "Date", "Signed By Name"];
const DEFAULT_BOX_FRACTION = {
	Signature: { x: 0.05, y: 0.75, width: 0.3, height: 0.1 },
	Date: { x: 0.05, y: 0.87, width: 0.2, height: 0.05 },
	"Signed By Name": { x: 0.4, y: 0.75, width: 0.3, height: 0.05 },
};
const PLACEMENT_PAGE_WIDTH = 640; // px — fixed display width for every page inside the dialog

frappe.ui.form.on("Proposal", {
	refresh(frm) {
		apply_template_sections(frm);
		add_pull_button(frm);
		add_place_signature_button(frm);
		add_send_for_signature_button(frm);
		set_create_flow_intro(frm);
		set_status_indicator(frm);
		add_signature_status_indicator(frm);
		render_section_progress(frm);
		relabel_add_section_button(frm);
	},
	proposal_template(frm) {
		apply_template_sections(frm);
	},
});

// Fires whenever an Additional Sections row is expanded into its full
// edit form (the card view's `additional_section_grid.html` shows a
// preview only — this is where the actual editing happens). Jump the
// cursor straight into Content, since Section Label is usually already
// filled in by the time someone opens a row to write its body.
frappe.ui.form.on("Proposal Additional Section", {
	form_render(frm) {
		const grid_row = frappe.ui.form.get_open_grid_form();
		const content_field = grid_row && grid_row.grid_form.fields_dict.content;
		if (content_field && content_field.quill) {
			setTimeout(() => content_field.quill.focus(), 200);
		}
	},
});

function relabel_add_section_button(frm) {
	const grid = frm.fields_dict.additional_sections && frm.fields_dict.additional_sections.grid;
	if (grid) {
		grid.wrapper.find(".grid-add-row").text(__("+ Add Section"));
	}
}

function set_create_flow_intro(frm) {
	if (!frm.is_new()) return;
	frm.set_intro(
		__(
			"Set Bid and Template, then save — you'll be able to pull ready content from each Lead's workstream output."
		),
		"blue"
	);
}

function set_status_indicator(frm) {
	frm.page.set_indicator(__(frm.doc.status), STATUS_COLORS[frm.doc.status] || "blue");
}

function add_signature_status_indicator(frm) {
	// A second, separate badge (not frm.page.set_indicator, which would
	// clobber the Draft/Final/Sent/Superseded one above) — only shown
	// once something has actually happened, not for the default
	// "Not Sent" state every Proposal starts in.
	if (frm.is_new() || !frm.doc.signature_status || frm.doc.signature_status === "Not Sent") return;
	frm.dashboard.add_indicator(
		__("Signature: {0}", [__(frm.doc.signature_status)]),
		SIGNATURE_STATUS_COLORS[frm.doc.signature_status] || "gray"
	);
}

function has_real_content(html) {
	// Quill's own "empty" state is `<p><br></p>`, not an empty string —
	// strip tags and check what text (if any) is actually left, same
	// reasoning as the server-side strip_html check in bid_workstream_output.py.
	if (!html) return false;
	return !!$("<div>").html(html).text().trim();
}

function render_section_progress(frm) {
	if (frm.is_new()) return;

	const filled = PROPOSAL_SECTION_FIELDS.filter((fieldname) => has_real_content(frm.doc[fieldname])).length;
	const extra = (frm.doc.additional_sections || []).length;
	const percent = Math.round((filled / PROPOSAL_SECTION_FIELDS.length) * 100);

	const message = extra
		? __("{0} of {1} core sections written, {2} additional section(s) added", [
				filled,
				PROPOSAL_SECTION_FIELDS.length,
				extra,
			])
		: __("{0} of {1} core sections written", [filled, PROPOSAL_SECTION_FIELDS.length]);

	frm.dashboard.add_progress(__("Section Progress"), percent, message);
}

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

function add_place_signature_button(frm) {
	// Visibility here is just a convenience, mirroring add_pull_button —
	// the real Bid Manager / Final-status checks are enforced server-side
	// in get_placement_preview / save_signature_placement.
	if (frm.is_new() || !frm.doc.bid || !frm.perm[0].write) return;
	if (frm.doc.status !== "Final") return;

	frm.add_custom_button(__("Place Signature"), () => {
		frm.call("get_placement_preview").then((r) => {
			if (!r.message || !r.message.pages || !r.message.pages.length) {
				frappe.msgprint(__("Could not render this proposal's pages."));
				return;
			}
			open_placement_dialog(frm, r.message.pages);
		});
	});
}

function open_placement_dialog(frm, pages) {
	const dialog = new frappe.ui.Dialog({
		title: __("Place Signature"),
		size: "large",
		fields: [{ fieldname: "placement_html", fieldtype: "HTML" }],
		primary_action_label: __("Save Placement"),
		primary_action: () => save_placement(frm, dialog),
	});

	let html = `<p class="text-muted small">${__(
		"Drag each box onto the document below, or use the toggles to add or remove one."
	)}</p><div class="signature-toggle-row" style="margin-bottom:10px; display:flex; gap:16px; flex-wrap:wrap;"></div>`;
	html += `<div class="placement-scroll" style="max-height:60vh; overflow-y:auto; border:1px solid var(--border-color, #d1d8dd); border-radius:6px; padding:10px;">`;
	html += `<div class="placement-pages" style="position:relative;">`;
	pages.forEach((page) => {
		const displayHeight = PLACEMENT_PAGE_WIDTH * (page.height / page.width);
		html += `
			<div class="placement-page" data-page="${page.page_number}" data-width-pt="${page.width}" data-height-pt="${page.height}"
				style="position:relative; width:${PLACEMENT_PAGE_WIDTH}px; height:${displayHeight}px; margin:0 auto 12px; background:#fff; box-shadow:0 1px 4px rgba(0,0,0,0.15);">
				<img src="${page.image}" style="width:100%; height:100%; display:block;">
			</div>`;
	});
	html += `</div></div>`;

	dialog.fields_dict.placement_html.$wrapper.html(html);

	const $toggleRow = dialog.$wrapper.find(".signature-toggle-row");
	const $wrapper = dialog.$wrapper.find(".placement-pages");
	const boxes = {};

	const existing = {};
	(frm.doc.signature_layout || []).forEach((row) => {
		existing[row.field_type] = row;
	});

	function default_placement(field_type) {
		const f = DEFAULT_BOX_FRACTION[field_type];
		const first = pages[0];
		return {
			page_number: first.page_number,
			x: f.x * first.width,
			y: f.y * first.height,
			width: f.width * first.width,
			height: f.height * first.height,
		};
	}

	// placement: {page_number, x, y, width, height} in PDF points —
	// converted here into on-screen pixels positioned relative to
	// .placement-pages (the shared coordinate frame every box lives in,
	// regardless of which page it's currently over).
	function add_box(field_type, placement) {
		const pageEl = $wrapper.find(`.placement-page[data-page="${placement.page_number}"]`)[0];
		if (!pageEl) return;
		const widthPt = parseFloat(pageEl.dataset.widthPt);
		const heightPt = parseFloat(pageEl.dataset.heightPt);

		const left = pageEl.offsetLeft + (placement.x / widthPt) * pageEl.offsetWidth;
		const top = pageEl.offsetTop + (placement.y / heightPt) * pageEl.offsetHeight;
		const width = (placement.width / widthPt) * pageEl.offsetWidth;
		const height = (placement.height / heightPt) * pageEl.offsetHeight;

		const $box = $(`
			<div class="placement-box" style="position:absolute; left:${left}px; top:${top}px; width:${width}px; height:${height}px; border:1.5px solid var(--tnl-600, #724b68); background:rgba(114,75,104,0.15); cursor:move; display:flex; align-items:center; justify-content:center; font-size:11px; color:var(--tnl-800, #4a2f42); user-select:none; z-index:5;">
				${__(field_type)}
				<div class="resize-handle" style="position:absolute; right:-4px; bottom:-4px; width:12px; height:12px; background:var(--tnl-600, #724b68); cursor:nwse-resize; border-radius:2px;"></div>
			</div>
		`);
		$wrapper.append($box);
		boxes[field_type] = $box;
		make_placement_box_draggable($box, $wrapper[0]);
	}

	function remove_box(field_type) {
		if (boxes[field_type]) {
			boxes[field_type].remove();
			delete boxes[field_type];
		}
	}

	SIGNATURE_FIELD_TYPES.forEach((field_type) => {
		const $toggle = $(`
			<label style="display:flex; align-items:center; gap:4px; font-weight:normal;">
				<input type="checkbox" ${existing[field_type] ? "checked" : ""}>
				${__(field_type)}
			</label>
		`);
		$toggleRow.append($toggle);

		$toggle.find("input").on("change", (e) => {
			if (e.target.checked) {
				add_box(field_type, existing[field_type] || default_placement(field_type));
			} else {
				remove_box(field_type);
			}
		});

		if (existing[field_type]) {
			add_box(field_type, existing[field_type]);
		}
	});

	dialog.get_placement_rows = () => get_placement_rows(boxes, $wrapper);
	dialog.show();
}

// Plain mousedown/mousemove/mouseup — no drag library, same as the rest
// of this app's hand-rolled interactions. Drag moves a box freely within
// the shared .placement-pages coordinate frame; which PAGE it's now over
// is only resolved once, at save time (get_placement_rows), not on every
// mousemove.
function make_placement_box_draggable($box, wrapperEl) {
	$box.on("mousedown", function (e) {
		if ($(e.target).hasClass("resize-handle")) return;
		e.preventDefault();
		const startX = e.pageX;
		const startY = e.pageY;
		const startLeft = parseFloat($box.css("left"));
		const startTop = parseFloat($box.css("top"));

		function on_move(ev) {
			const dx = ev.pageX - startX;
			const dy = ev.pageY - startY;
			const maxLeft = Math.max(0, wrapperEl.scrollWidth - $box.outerWidth());
			const maxTop = Math.max(0, wrapperEl.scrollHeight - $box.outerHeight());
			$box.css({
				left: Math.min(Math.max(0, startLeft + dx), maxLeft) + "px",
				top: Math.min(Math.max(0, startTop + dy), maxTop) + "px",
			});
		}
		function on_up() {
			$(document).off("mousemove", on_move).off("mouseup", on_up);
		}
		$(document).on("mousemove", on_move).on("mouseup", on_up);
	});

	$box.find(".resize-handle").on("mousedown", function (e) {
		e.preventDefault();
		e.stopPropagation();
		const startX = e.pageX;
		const startY = e.pageY;
		const startWidth = $box.outerWidth();
		const startHeight = $box.outerHeight();

		function on_move(ev) {
			$box.css({
				width: Math.max(30, startWidth + (ev.pageX - startX)) + "px",
				height: Math.max(18, startHeight + (ev.pageY - startY)) + "px",
			});
		}
		function on_up() {
			$(document).off("mousemove", on_move).off("mouseup", on_up);
		}
		$(document).on("mousemove", on_move).on("mouseup", on_up);
	});
}

// The one place per gesture (not per mousemove) that figures out which
// page a box now belongs to: walk each page div's own offsetTop/offsetHeight
// within the shared wrapper, find the range containing the box's
// vertical center (falling back to the nearest page if it's sitting in
// the gap between two), then convert that page-relative pixel position
// into PDF points using that page's own known width/height.
function get_placement_rows(boxes, $wrapper) {
	const pageEls = $wrapper.find(".placement-page").toArray();
	const rows = [];

	Object.keys(boxes).forEach((field_type) => {
		const $box = boxes[field_type];
		const boxLeft = parseFloat($box.css("left"));
		const boxTop = parseFloat($box.css("top"));
		const boxWidth = $box.outerWidth();
		const boxHeight = $box.outerHeight();
		const centerY = boxTop + boxHeight / 2;

		let target = pageEls.find((el) => centerY >= el.offsetTop && centerY <= el.offsetTop + el.offsetHeight);
		if (!target) {
			target = pageEls.reduce((closest, el) => {
				const dist = Math.min(Math.abs(centerY - el.offsetTop), Math.abs(centerY - (el.offsetTop + el.offsetHeight)));
				if (!closest) return el;
				const closestDist = Math.min(
					Math.abs(centerY - closest.offsetTop),
					Math.abs(centerY - (closest.offsetTop + closest.offsetHeight))
				);
				return dist < closestDist ? el : closest;
			}, null);
		}
		if (!target) return;

		const widthPt = parseFloat(target.dataset.widthPt);
		const heightPt = parseFloat(target.dataset.heightPt);

		rows.push({
			field_type,
			page_number: parseInt(target.dataset.page, 10),
			x: ((boxLeft - target.offsetLeft) / target.offsetWidth) * widthPt,
			y: ((boxTop - target.offsetTop) / target.offsetHeight) * heightPt,
			width: (boxWidth / target.offsetWidth) * widthPt,
			height: (boxHeight / target.offsetHeight) * heightPt,
		});
	});

	return rows;
}

function save_placement(frm, dialog) {
	const rows = dialog.get_placement_rows();
	if (!rows.some((row) => row.field_type === "Signature")) {
		frappe.msgprint(__("Add a Signature box before saving."));
		return;
	}
	frm.call("save_signature_placement", { rows }).then(() => {
		dialog.hide();
		frm.reload_doc();
		frappe.show_alert({ message: __("Signature placement saved."), indicator: "green" });
	});
}

function add_send_for_signature_button(frm) {
	// Visibility here is just a convenience, mirroring add_pull_button —
	// the real Bid Manager / Final-status / not-already-sent / has-a-
	// designed-signature-area checks are enforced server-side in
	// send_for_signature.
	if (frm.is_new() || !frm.doc.bid || !frm.perm[0].write) return;
	if (frm.doc.status !== "Final") return;
	if (frm.doc.signature_status !== "Not Sent") return;

	frm.add_custom_button(__("Send for Signature"), () => {
		frappe.confirm(__("Send this proposal to the client for e-signature?"), () => {
			frm.call("send_for_signature").then(() => {
				frm.reload_doc();
				frappe.show_alert({ message: __("Sent for signature."), indicator: "blue" });
			});
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
