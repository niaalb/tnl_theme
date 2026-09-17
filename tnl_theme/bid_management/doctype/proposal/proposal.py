# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import strip_html

WORKSTREAM_PROPOSAL_FIELD = {
	"Technical": "technical_approach",
	"Financial": "commercial_terms",
	"Administrative": "compliance_statement",
}

# Renders each Additional Sections row as a small labeled card (heading +
# a truncated content preview) instead of Frappe's default spreadsheet-style
# grid row — the same mechanism ERPNext itself uses for Item rows (e.g.
# quotation.py, sales_order.py). Only takes effect while the child doctype's
# own editable_grid is off (see proposal_additional_section.json).
form_grid_templates = {"additional_sections": "templates/form_grid/additional_section_grid.html"}


class Proposal(Document):
	def validate(self):
		self._check_signature_layout_has_no_duplicate_field_types()

	def _check_signature_layout_has_no_duplicate_field_types(self):
		seen = set()
		for row in self.signature_layout:
			if row.field_type in seen:
				frappe.throw(_("Signature Layout can only have one {0} box.").format(row.field_type))
			seen.add(row.field_type)

	def before_insert(self):
		existing_count = frappe.db.count("Proposal", {"bid": self.bid})
		self.version = existing_count + 1

		# An unfilled title shows up blank in list view, breadcrumbs, and
		# every link field pointing to this Proposal — give it something
		# readable by default, same spirit as the letter_head default
		# below. Still fully editable afterward.
		if not self.title:
			client_account = frappe.db.get_value("Bid", self.bid, "client_account")
			self.title = f"{client_account or self.bid} — Proposal v{self.version}"

		# Frappe auto-fills any field literally named "letter_head" from a
		# site-wide sticky default (tabDefaultValue) before this hook runs,
		# so `self.letter_head` is never actually empty here — an emptiness
		# check would always lose to that generic default. The template's
		# own default has to win outright; users can still edit the field
		# by hand after the Proposal is created.
		if self.proposal_template:
			template_default = frappe.db.get_value(
				"Proposal Template", self.proposal_template, "default_letter_head"
			)
			if template_default:
				self.letter_head = template_default

	def on_update(self):
		if self.status != "Sent":
			return
		# At most one "live" sent proposal per Bid — anything else that
		# was Final for the same Bid is now superseded by this one.
		frappe.db.set_value(
			"Proposal",
			{"bid": self.bid, "status": "Final", "name": ["!=", self.name]},
			"status",
			"Superseded",
		)

	@frappe.whitelist()
	def pull_workstream_outputs(self):
		"""Copy each ready Bid Workstream Output's content into the
		matching Proposal section. Deliberately a one-time, explicit
		copy-in rather than a live link: it only ever reads from the
		source workstream documents (never writes back to them), and it
		only ever fills a Proposal field that's still empty (never
		overwrites one already written), so an edit on either side
		afterward can't silently ripple onto the other — a Lead updating
		their output later doesn't change a Proposal already built from
		an earlier version of it, and nothing here can touch the source
		document at all.

		Bid Manager-only (not just "has Proposal write", which Business
		Development and Sales also have) — consolidating source material
		into the client-facing document is specifically the Bid Manager's
		call, same responsibility split as everywhere else in Bid
		Management.
		"""
		self._check_can_pull()

		outputs = frappe.get_all(
			"Bid Workstream Output",
			filters={"bid": self.bid, "ready_for_proposal": 1},
			fields=["workstream", "content"],
		)
		ready_content = {o.workstream: o.content for o in outputs}

		pulled, skipped_not_ready, skipped_has_content = [], [], []
		for workstream, fieldname in WORKSTREAM_PROPOSAL_FIELD.items():
			if strip_html(self.get(fieldname) or "").strip():
				skipped_has_content.append(workstream)
				continue
			content = ready_content.get(workstream)
			if not content:
				skipped_not_ready.append(workstream)
				continue
			self.set(fieldname, content)
			pulled.append(workstream)

		if pulled:
			self.save()

		return {
			"pulled": pulled,
			"skipped_not_ready": skipped_not_ready,
			"skipped_has_content": skipped_has_content,
		}

	def _check_can_pull(self):
		if not self.bid:
			frappe.throw(_("Set Bid before pulling workstream outputs."))

		user = frappe.session.user
		if user == "Administrator" or "System Manager" in frappe.get_roles(user):
			return
		if user != frappe.db.get_value("Bid", self.bid, "bid_manager"):
			frappe.throw(_("Only this Bid's Bid Manager may pull workstream outputs into the Proposal."))

	@frappe.whitelist()
	def send_for_signature(self):
		"""Email the client a link to the guest signing page (tnl_theme's
		own /sign-proposal, not a third-party provider) and mark this
		Proposal as sent. Queues the email rather than sending it
		synchronously (no `now=True`) — the status change and share-key
		link this method produces are the important, durable part, and
		shouldn't fail outright just because outgoing email is briefly
		unavailable; delivery can catch up via the normal mail queue.

		Bid Manager-only, same responsibility split as pull_workstream_outputs.
		"""
		self._check_can_send_for_signature()

		key = self.get_document_share_key()
		link = f"{frappe.utils.get_url()}/sign-proposal?proposal={self.name}&key={key}"
		client_email = frappe.db.get_value("Bid", self.bid, "client_contact_email")

		frappe.sendmail(
			recipients=[client_email],
			subject=_("Please review and sign: {0}").format(self.title or self.name),
			message=_(
				"{0} has sent you the proposal <b>{1}</b> for review and signature.<br><br>"
				"<a href='{2}'>Click here to review and sign</a>"
			).format(frappe.utils.get_fullname(frappe.session.user), self.title or self.name, link),
			reference_doctype=self.doctype,
			reference_name=self.name,
		)

		self.status = "Sent"
		self.signature_status = "Sent"
		self.save()

	def _check_can_send_for_signature(self):
		if not self.bid:
			frappe.throw(_("Set Bid before sending for signature."))
		if self.status != "Final":
			frappe.throw(_("Only a Final proposal can be sent for signature."))
		if self.signature_status != "Not Sent":
			frappe.throw(_("This proposal has already been sent for signature."))
		if not frappe.db.get_value("Bid", self.bid, "client_contact_email"):
			frappe.throw(_("Set a Client Contact Email on the Bid before sending for signature."))
		if not frappe.db.exists("Proposal Signature Field", {"parent": self.name, "field_type": "Signature"}):
			frappe.throw(_('This Proposal has no Signature placed yet — use "Place Signature" first.'))
		self._check_placement_not_stale()

		user = frappe.session.user
		if user == "Administrator" or "System Manager" in frappe.get_roles(user):
			return
		if user != frappe.db.get_value("Bid", self.bid, "bid_manager"):
			frappe.throw(_("Only this Bid's Bid Manager may send it for signature."))

	def _check_placement_not_stale(self):
		"""Nothing stops editing a Proposal's content after Final today (no
		submit workflow on this doctype) — if that happens after fields
		were placed, a stored page_number could point past the end of the
		freshly-rendered document. Fails loud (not the usual best-effort
		try/except this app uses for side effects like logging) because
		this protects the correctness of the actual document being
		produced, not a convenience."""
		from tnl_theme.bid_management import signature_placement

		page_count = len(signature_placement.inspect_pages(signature_placement.render_base_pdf(self)))
		max_placed = max((row.page_number for row in self.signature_layout), default=0)
		if max_placed > page_count:
			frappe.throw(
				_(
					'This Proposal\'s content has changed since the signature was placed — use "Place Signature" again before sending.'
				)
			)

	@frappe.whitelist()
	def get_placement_preview(self):
		"""Renders this Proposal to PDF and rasterizes each page to an
		image for the "Place Signature" dialog — everything the dialog
		needs in one call, with no File attachments for these ephemeral
		previews (they're regenerated on demand, never stored).

		Bid Manager-only, same responsibility split as pull_workstream_outputs."""
		import base64

		from tnl_theme.bid_management import signature_placement

		self._check_can_place_signature()

		pdf_bytes = signature_placement.render_base_pdf(self)
		pages = signature_placement.inspect_pages(pdf_bytes)
		images = signature_placement.rasterize_pages(pdf_bytes)

		for page in pages:
			png_bytes = images[page["page_number"]]
			page["image"] = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

		return {"pages": pages}

	@frappe.whitelist()
	def save_signature_placement(self, rows):
		"""Replaces this Proposal's entire signature_layout with the
		posted rows — always a full replace, never a partial merge, since
		the placement dialog always re-saves every box it currently shows."""
		self._check_can_place_signature()

		self.set("signature_layout", [])
		for row in frappe.parse_json(rows) if isinstance(rows, str) else rows:
			self.append(
				"signature_layout",
				{
					"field_type": row["field_type"],
					"page_number": row["page_number"],
					"x": row["x"],
					"y": row["y"],
					"width": row["width"],
					"height": row["height"],
				},
			)
		self.save()

	def _check_can_place_signature(self):
		if self.status != "Final":
			frappe.throw(_("Only a Final proposal can have its signature placed."))

		user = frappe.session.user
		if user == "Administrator" or "System Manager" in frappe.get_roles(user):
			return
		if user != frappe.db.get_value("Bid", self.bid, "bid_manager"):
			frappe.throw(_("Only this Bid's Bid Manager may place the signature."))
