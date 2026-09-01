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


class Proposal(Document):
	def before_insert(self):
		existing_count = frappe.db.count("Proposal", {"bid": self.bid})
		self.version = existing_count + 1

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
