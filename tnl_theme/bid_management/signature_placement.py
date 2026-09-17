"""PDF page rasterization and post-render signature compositing for
Proposal's e-signature flow.

Odoo Sign drags fields onto a static uploaded PDF, where a page/position
always exists in advance. A Proposal is dynamically generated per
document (section lengths vary), so there's no known page layout until
it's actually rendered — placement has to happen after rendering, and a
captured signature has to be composited into an already-rendered PDF
afterward, not injected into HTML before conversion (which is how the
previous, generic-zone version of this feature worked).

Pure helper functions only — no @frappe.whitelist, no permission
elevation of its own. Elevation stays at each call site next to its
actual authorization check (proposal.py's _check_can_place_signature,
signing.py's guest-facing entrypoints), so this module can't silently
become a privilege-escalation shortcut.
"""

import io

import frappe
from frappe import _

IMAGE_FIELD_TYPES = {"Signature"}


def render_base_pdf(doc):
	"""The Proposal's own content, unmodified — the signature is never
	baked into this render. Exists as its own function so there's exactly
	one call site to change later, and an easy seam for tests."""
	return frappe.get_print(doc.doctype, doc.name, "Proposal Standard", as_pdf=True)


def inspect_pages(pdf_bytes):
	"""Page count and each page's real size in PDF points. 1-based, to
	match rasterize_pages' own convention below — deliberately kept
	consistent so the two can't quietly disagree with each other."""
	from pypdf import PdfReader

	reader = PdfReader(io.BytesIO(pdf_bytes))
	return [
		{"page_number": i + 1, "width": float(page.mediabox.width), "height": float(page.mediabox.height)}
		for i, page in enumerate(reader.pages)
	]


def rasterize_pages(pdf_bytes, resolution=120):
	"""Renders each page to a PNG for the placement dialog / guest signing
	page to display. Same technique ERPNext's own bank statement importer
	already uses (erpnext/accounts/doctype/bank_statement_import_log/
	bank_statement_import_log.py::render_pdf_pages) — pdfplumber's
	Page.to_image() via its pypdfium2 render backend. Returns
	{page_number: png_bytes}, 1-based."""
	import pdfplumber

	images = {}
	with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
		for i, page in enumerate(pdf.pages, start=1):
			buffer = io.BytesIO()
			page.to_image(resolution=resolution).original.save(buffer, format="PNG")
			images[i] = buffer.getvalue()
	return images


def build_page_overlay_html(width_pt, height_pt, fields):
	"""One absolutely-positioned element per field, all on a single blank
	page. Deliberately no page-size CSS here at all (no @page{} rule) —
	frappe.utils.pdf.get_pdf() never reads that; page geometry is supplied
	separately as plain options to render_overlay_pdf below.

	`fields`: [{x, y, width, height, value, value_type}], value_type
	"image" (a data: URI) or "text". `y` is measured from the TOP of the
	page — matching on-screen/CSS convention, and exactly how Proposal
	Signature Field stores it, and how the placement dialog and the
	guest signing page both already position boxes with no flip. This
	HTML is rendered by wkhtmltopdf via ordinary CSS `top:`, which is
	already top-left-origin — wkhtmltopdf does its own conversion to
	PDF's internal bottom-left coordinate system, so `field["y"]` is used
	directly here. (An earlier version of this function flipped it,
	treating it as if this were raw PDF content-stream coordinate math —
	that only applies when drawing directly with pypdf's low-level
	transformation APIs, not when generating HTML for wkhtmltopdf to
	render, and the extra flip put every field at `height_pt - y`
	instead of `y`.)"""
	import html as html_lib

	parts = ['<html><body style="margin:0; padding:0;">']
	for field in fields:
		style = (
			f'position:absolute; left:{field["x"]}pt; top:{field["y"]}pt; '
			f'width:{field["width"]}pt; height:{field["height"]}pt;'
		)
		if field["value_type"] == "image":
			parts.append(f'<img src="{field["value"]}" style="{style} object-fit:contain;">')
		else:
			text_style = style + " font-family:Helvetica,Arial,sans-serif; font-size:10pt; color:#000;"
			parts.append(f'<div style="{text_style}">{html_lib.escape(field["value"])}</div>')
	parts.append("</body></html>")
	return "".join(parts)


def render_overlay_pdf(html, width_pt, height_pt):
	"""The one call that builds a single-page PDF sized to exactly match a
	target page. Calls pdfkit directly rather than frappe.utils.pdf.get_pdf()
	— confirmed against the real bench (not assumed) that get_pdf()'s own
	prepare_options() has a real bug for this use case: passing
	"page-size": "Custom" (its own documented way to say "use my
	page-width/page-height instead of the site default") leaves that
	literal string "Custom" in the options dict, which then gets forwarded
	straight to wkhtmltopdf's CLI as `--page-size Custom` — which
	wkhtmltopdf rejects outright ("Invalid argument(s) parsed to
	--page-size"), since it only ever wants page-width/page-height alone
	with no --page-size flag at all for a custom size, not a "Custom"
	sentinel. Going around get_pdf() entirely sidesteps this — this tiny,
	self-contained overlay HTML doesn't need any of get_pdf()'s other
	batteries anyway (cookies, header/footer, external URL handling).

	All four margin properties are still written out longhand rather than
	as a `margin` shorthand — harmless here since no CSS is being
	sniffed from HTML at all (that's a get_pdf()-specific mechanism this
	call no longer goes through), but kept for clarity and consistency.
	"""
	import pdfkit

	options = {
		"page-width": f"{width_pt}pt",
		"page-height": f"{height_pt}pt",
		"margin-top": "0mm",
		"margin-right": "0mm",
		"margin-bottom": "0mm",
		"margin-left": "0mm",
		"disable-javascript": "",
		"disable-local-file-access": "",
		"quiet": "",
	}
	return pdfkit.from_string(html, options=options)


def compose_signed_pdf(base_pdf_bytes, signature_layout_rows, field_values):
	"""Merges every placed field into its target page of the base PDF —
	doc-agnostic; `field_values` is a plain {field_type: value} dict the
	caller resolves (e.g. {"Signature": "data:image/png;base64,...",
	"Date": "14 Sep 2026", "Signed By Name": "Jordan Client"}).

	One overlay render per PAGE, not per field — fewer wkhtmltopdf
	subprocess calls, and every field on a page shares one deterministic
	coordinate frame instead of trusting N separate renders to agree with
	each other.

	Throws if placement has gone stale (a stored page_number past the end
	of this actual render) — fails loud, phrased for whoever is actually
	signing right now, since content could change between Send for
	Signature and the client opening the link (proposal.py's own
	_check_placement_not_stale covers the earlier, Bid-Manager-facing
	case at send time)."""
	from pypdf import PdfReader, PdfWriter

	base_reader = PdfReader(io.BytesIO(base_pdf_bytes))
	page_count = len(base_reader.pages)

	by_page = {}
	for row in signature_layout_rows:
		if row.page_number > page_count:
			frappe.throw(
				_(
					"This proposal's content has changed since the signature was placed — contact the sender for a new link."
				)
			)
		by_page.setdefault(row.page_number, []).append(row)

	writer = PdfWriter()
	writer.append_pages_from_reader(base_reader)

	for page_number, rows in by_page.items():
		base_page = writer.pages[page_number - 1]
		width_pt = float(base_page.mediabox.width)
		height_pt = float(base_page.mediabox.height)

		fields = []
		for row in rows:
			value = field_values.get(row.field_type)
			if not value:
				continue
			fields.append(
				{
					"x": row.x,
					"y": row.y,
					"width": row.width,
					"height": row.height,
					"value": value,
					"value_type": "image" if row.field_type in IMAGE_FIELD_TYPES else "text",
				}
			)
		if not fields:
			continue

		overlay_html = build_page_overlay_html(width_pt, height_pt, fields)
		overlay_bytes = render_overlay_pdf(overlay_html, width_pt, height_pt)
		overlay_page = PdfReader(io.BytesIO(overlay_bytes)).pages[0]
		# Belt-and-suspenders exact-dimension guarantee regardless of any
		# wkhtmltopdf unit-rounding in the overlay render above.
		overlay_page.scale_to(width_pt, height_pt)
		base_page.merge_page(overlay_page)

	output = io.BytesIO()
	writer.write(output)
	return output.getvalue()
