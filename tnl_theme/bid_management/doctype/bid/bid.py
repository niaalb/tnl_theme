# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from tnl_theme.bid_management.utils import add_business_days

CHECKPOINT_ESCALATION_FLAG = {
	"technical_next_checkpoint_date": "escalated_technical",
	"financial_next_checkpoint_date": "escalated_financial",
	"administrative_next_checkpoint_date": "escalated_administrative",
}

# Frappe's field-level permlevel is role-based, not instance-based — anyone
# holding "Technical Lead" globally could otherwise edit technical_status on
# ANY Bid, not just the ones where they're the named lead. This map drives
# the extra per-document ownership check in validate().
WORKSTREAM_OWNER_FIELD = {
	"technical_status": "technical_lead",
	"technical_next_checkpoint_date": "technical_lead",
	"financial_status": "financial_lead",
	"financial_next_checkpoint_date": "financial_lead",
	"administrative_status": "administrative_lead",
	"administrative_next_checkpoint_date": "administrative_lead",
}


class Bid(Document):
	def validate(self):
		self._enforce_workstream_ownership()
		self._require_reasoning()
		self._track_handoff_timestamps()
		self._reset_escalation_flags_on_new_checkpoint()

	def on_update(self):
		self._notify_on_stage_change()

	def _enforce_workstream_ownership(self):
		user = frappe.session.user
		if user == "Administrator" or "System Manager" in frappe.get_roles(user):
			return
		if user == self.bid_manager:
			return

		before = self.get_doc_before_save()
		if not before:
			return

		for field, owner_field in WORKSTREAM_OWNER_FIELD.items():
			if self.get(field) != before.get(field) and user != self.get(owner_field):
				frappe.throw(
					_("Only the assigned {0} may update {1}.").format(
						self.meta.get_label(owner_field), self.meta.get_label(field)
					)
				)

	def _require_reasoning(self):
		if self.bid_no_bid_decision and not self.qualification_reasoning:
			frappe.throw(_("Qualification Reasoning is required when a Bid / No-Bid Decision is set."))
		if self.outcome and not self.outcome_reasoning:
			frappe.throw(_("Outcome Reasoning is required when an Outcome is set."))

	def _track_handoff_timestamps(self):
		"""Stamp the hand-off clock the moment BD hands off, and Sales's
		acknowledgment the moment they confirm receipt — these drive the
		escalation job in bid_management/tasks.py and the hand-off SLA
		KPI reports."""
		before = self.get_doc_before_save()
		if not before:
			return

		if self.stage == "Handed Off" and before.stage != "Handed Off":
			self.handoff_date = self.handoff_date or frappe.utils.today()
			self.handoff_escalation_due = add_business_days(self.handoff_date, 2)
			self.handoff_escalated = 0

		if self.stage == "Qualifying" and before.stage == "Handed Off":
			self.handoff_acknowledged_on = frappe.utils.now_datetime()

	def _reset_escalation_flags_on_new_checkpoint(self):
		"""Once a lead logs a new next-checkpoint date, re-arm that
		workstream's escalation flag so a past overdue notice doesn't
		suppress a fresh one against the new date."""
		before = self.get_doc_before_save()
		if not before:
			return

		for date_field, flag_field in CHECKPOINT_ESCALATION_FLAG.items():
			if self.get(date_field) != before.get(date_field):
				self.set(flag_field, 0)

	def _notify_on_stage_change(self):
		"""Ping the right person the moment a bid actually lands on their
		desk, rather than leaving every hand-off/assignment silent until
		someone happens to notice the stage changed. Deliberately separate
		from tasks.py's overdue-escalation emails — this covers the normal,
		on-time path; escalations remain the only thing that goes to email,
		since outgoing mail isn't configured on every site this runs on and
		these routine pings need to work without it."""
		before = self.get_doc_before_save()
		if not before or before.stage == self.stage:
			return

		if self.stage == "Handed Off":
			self._assign_todo(
				[self.sales_owner],
				_("Bid {0} ({1}) has been handed off to you — please acknowledge receipt.").format(
					self.name, self.client_account
				),
			)
		elif self.stage == "In Progress":
			for user, role_label in (
				(self.technical_lead, _("Technical Lead")),
				(self.financial_lead, _("Financial Lead")),
				(self.administrative_lead, _("Administrative Lead")),
			):
				self._assign_todo(
					[user],
					_("You've been assigned as {0} on Bid {1} ({2}).").format(
						role_label, self.name, self.client_account
					),
				)
		elif self.stage == "Submitted":
			self._notify_alert(
				[self.sales_owner],
				_("Bid {0} ({1}) has been submitted to the client.").format(self.name, self.client_account),
			)
		elif self.stage == "Closed" and self.outcome:
			self._notify_alert(
				[self.bid_manager, self.technical_lead, self.financial_lead, self.administrative_lead],
				_("Outcome recorded for Bid {0} ({1}): {2}.").format(
					self.name, self.client_account, self.outcome
				),
			)

	def _assign_todo(self, users, description):
		from frappe.desk.form.assign_to import add as assign_to_add

		users = [u for u in users if u]
		if not users:
			return
		assign_to_add(
			{
				"assign_to": users,
				"doctype": self.doctype,
				"name": self.name,
				"description": description,
			}
		)

	def _notify_alert(self, users, subject):
		from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

		users = [u for u in users if u]
		if not users:
			return
		enqueue_create_notification(
			users,
			{
				"type": "Alert",
				"document_type": self.doctype,
				"document_name": self.name,
				"subject": subject,
				"from_user": frappe.session.user,
			},
		)
