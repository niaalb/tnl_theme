import base64

import frappe

from tnl_theme.bid_management import signature_placement, signing

no_cache = 1


def get_context(context):
	"""Guest-accessible signing page, reached at /sign-proposal?proposal=
	<name>&key=<Document Share Key>. Shows the Proposal's actual rendered
	pages as images (the same rasterization used by the "Place Signature"
	dialog on the Proposal form) rather than embedding print-format HTML —
	placement is per real page/position now, not a generic zone, so the
	page the client sees has to be the same one fields were placed on."""
	proposal_name = frappe.form_dict.get("proposal")
	key = frappe.form_dict.get("key")

	context.no_cache = 1

	if not proposal_name or not signing.validate_key(proposal_name, key):
		context.invalid_link = True
		return context

	doc = frappe.get_doc("Proposal", proposal_name)
	context.doc = doc
	context.key = key
	context.proposal_name = proposal_name
	context.already_decided = doc.signature_status in ("Signed", "Declined")
	layout_rows = (
		[]
		if context.already_decided
		else [
			{
				"field_type": row.field_type,
				"page_number": row.page_number,
				"x": row.x,
				"y": row.y,
				"width": row.width,
				"height": row.height,
			}
			for row in doc.signature_layout
		]
	)
	context.signature_layout_json = frappe.as_json(layout_rows)

	if not context.already_decided:
		signing.record_view(proposal_name)

	# Reading the base PDF (frappe.get_print's own internal permission
	# check) and, once signed, the private signed_document File both need
	# more than Guest has — a valid Document Share Key (already confirmed
	# above) is exactly the authorization this page runs on, so briefly
	# elevating here rather than depending on any incidental key-matching
	# path elsewhere is the explicit, robust choice.
	current_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		if doc.signature_status == "Signed" and doc.signed_document:
			# Show what was actually signed — the composited PDF with the
			# real signature baked in — not a fresh, unsigned re-render.
			pdf_bytes = frappe.get_doc("File", {"file_url": doc.signed_document}).get_content()
		else:
			pdf_bytes = signature_placement.render_base_pdf(doc)
		pages = signature_placement.inspect_pages(pdf_bytes)
		images = signature_placement.rasterize_pages(pdf_bytes)
	finally:
		frappe.set_user(current_user)

	for page in pages:
		png_bytes = images[page["page_number"]]
		page["image"] = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
	context.pages = pages

	return context
