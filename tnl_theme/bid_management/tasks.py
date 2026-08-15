import frappe
from frappe.utils import getdate, today

WORKSTREAM_FIELDS = [
	("technical", "technical_status", "technical_next_checkpoint_date", "escalated_technical", "Technical Lead"),
	("financial", "financial_status", "financial_next_checkpoint_date", "escalated_financial", "Financial Lead"),
	(
		"administrative",
		"administrative_status",
		"administrative_next_checkpoint_date",
		"escalated_administrative",
		"Administrative Lead",
	),
]


def check_bid_escalations():
	"""Daily scheduler job (registered in hooks.py) implementing the
	policy's two automatable escalation rules. A custom job rather than
	Frappe's built-in Notification doctype, since Notification's date
	offsets are calendar days only and the client's rule is business
	days (see handoff_escalation_due, computed with add_business_days
	in bid.py)."""
	_escalate_handoffs()
	_escalate_workstream_checkpoints()


def _escalate_handoffs():
	overdue = frappe.get_all(
		"Bid",
		filters={
			"stage": "Handed Off",
			"handoff_escalated": 0,
			"handoff_escalation_due": ["<=", today()],
		},
		fields=["name", "bd_owner"],
	)
	if not overdue:
		return

	bid_managers = frappe.get_all("Has Role", filters={"role": "Bid Manager"}, pluck="parent")

	for bid in overdue:
		recipients = list({*bid_managers, bid.bd_owner})
		try:
			frappe.sendmail(
				recipients=recipients,
				subject=f"[Escalation] Bid {bid.name}: hand-off not acknowledged",
				message=(
					f"Bid {bid.name} was handed off to Sales more than 2 business days ago "
					"and hasn't been acknowledged yet."
				),
			)
			frappe.db.set_value("Bid", bid.name, "handoff_escalated", 1)
		except Exception:
			# One bid's email failure (e.g. no outgoing Email Account
			# configured yet) shouldn't block escalating the rest.
			frappe.log_error(title=f"Bid hand-off escalation failed: {bid.name}")


def _escalate_workstream_checkpoints():
	for prefix, status_field, date_field, flag_field, role_label in WORKSTREAM_FIELDS:
		overdue = frappe.get_all(
			"Bid",
			filters={
				"stage": "In Progress",
				status_field: ["not in", ["Completed", "On Hold"]],
				flag_field: 0,
				# "is set" guards against an empty checkpoint date (a
				# workstream whose lead hasn't committed to one yet) being
				# compared as "<= today" and matching by accident.
				date_field: ["is", "set"],
			},
			fields=["name", "bid_manager", date_field],
		)
		overdue = [b for b in overdue if getdate(b.get(date_field)) <= getdate(today())]
		for bid in overdue:
			try:
				if bid.bid_manager:
					frappe.sendmail(
						recipients=[bid.bid_manager],
						subject=f"[Escalation] Bid {bid.name}: {role_label} checkpoint overdue",
						message=(
							f"No checkpoint update has been logged for the {prefix} workstream "
							f"on Bid {bid.name}, past its agreed checkpoint date."
						),
					)
				frappe.db.set_value("Bid", bid.name, flag_field, 1)
			except Exception:
				frappe.log_error(title=f"Bid workstream escalation failed: {bid.name} ({prefix})")
