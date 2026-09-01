# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import strip_html

WORKSTREAM_LEAD_FIELD = {
	"Technical": "technical_lead",
	"Financial": "financial_lead",
	"Administrative": "administrative_lead",
}


class BidWorkstreamOutput(Document):
	def validate(self):
		self._enforce_ownership()
		self._enforce_one_row_per_workstream()
		self._lock_bid_and_workstream()
		self._require_content_for_ready()
		self._stamp_ready_on()

	def _enforce_ownership(self):
		"""Runs on insert too, not just update — unlike Bid's own
		_enforce_workstream_ownership, which can skip insert because only
		BD/System Manager can create a Bid at all (role-gated at the
		doctype permission level already). Here the three Lead roles also
		get `create`, as a self-serve fallback for when the Kickoff
		auto-creation hook in bid.py doesn't fire — so nothing else would
		stop a Lead creating a row for a workstream they don't own if this
		check only covered update.
		"""
		if self.flags.ignore_permissions:
			# System-triggered creation (Bid's own Kickoff auto-creation
			# hook) isn't attributable to whichever user happened to be
			# the one confirming Kickoff — same trust boundary as every
			# other ignore_permissions=True insert already used for
			# hook-triggered records in this codebase (create_bid_from_lead
			# in api.py, for instance).
			return
		if not self.bid or not self.workstream:
			return

		user = frappe.session.user
		if user == "Administrator" or "System Manager" in frappe.get_roles(user):
			return

		bid = frappe.db.get_value(
			"Bid",
			self.bid,
			["bid_manager", "technical_lead", "financial_lead", "administrative_lead"],
			as_dict=True,
		)
		if not bid:
			return
		if user == bid.bid_manager:
			return

		owner_field = WORKSTREAM_LEAD_FIELD.get(self.workstream)
		if owner_field and user != bid.get(owner_field):
			frappe.throw(
				_("Only the assigned {0} for this Bid may edit its {1} workstream output.").format(
					frappe.get_meta("Bid").get_label(owner_field), self.workstream
				)
			)

	def _enforce_one_row_per_workstream(self):
		if not self.is_new() or not self.bid or not self.workstream:
			return
		if frappe.db.exists("Bid Workstream Output", {"bid": self.bid, "workstream": self.workstream}):
			frappe.throw(
				_("A {0} workstream output already exists for Bid {1}.").format(self.workstream, self.bid)
			)

	def _lock_bid_and_workstream(self):
		before = self.get_doc_before_save()
		if not before:
			return
		if self.bid != before.bid or self.workstream != before.workstream:
			frappe.throw(_("Bid and Workstream cannot be changed after creation."))

	def _require_content_for_ready(self):
		"""Checking the truthiness of self.content isn't enough — Quill's
		own "empty" state is `<p><br></p>`, not an empty string, so a
		blank document would otherwise pass a plain if-not-content check.
		Stripping tags first means only actual typed text counts."""
		if self.ready_for_proposal and not strip_html(self.content or "").strip():
			frappe.throw(_("Add the workstream output content before marking it Ready for Proposal."))

	def _stamp_ready_on(self):
		"""Set the moment Ready for Proposal is first checked; cleared if
		it's unchecked again for rework, the same reset-on-change idiom
		Bid itself uses for its escalation flags."""
		before = self.get_doc_before_save()
		was_ready = bool(before.ready_for_proposal) if before else False
		if self.ready_for_proposal and not was_ready:
			self.ready_on = frappe.utils.now_datetime()
		elif not self.ready_for_proposal and was_ready:
			self.ready_on = None
