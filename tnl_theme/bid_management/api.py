import frappe
from frappe import _


@frappe.whitelist()
def create_bid_from_deal(deal):
	"""Create a Bid pre-filled from a CRM Deal.

	Called by the "Create Bid" button (a CRM Form Script) on CRM Deal.
	Idempotent: if a Bid already links to this Deal, returns that one
	instead of creating a duplicate, since the button gives no other way
	to tell whether a Bid was already started for a given Deal.
	"""
	if not frappe.has_permission("Bid", "create"):
		frappe.throw(_("You are not permitted to create a Bid."), frappe.PermissionError)

	existing = frappe.db.get_value("Bid", {"crm_deal": deal}, "name")
	if existing:
		return {"name": existing, "created": False}

	deal_doc = frappe.get_doc("CRM Deal", deal)

	# If this Deal was converted from a Lead that already has a Bid (most
	# likely auto-created when that Lead was qualified — see
	# on_lead_status_change below), attach this Deal to that Bid instead
	# of creating a second one for the same underlying opportunity.
	if deal_doc.lead:
		existing_from_lead = frappe.db.get_value("Bid", {"crm_lead": deal_doc.lead}, "name")
		if existing_from_lead:
			frappe.db.set_value("Bid", existing_from_lead, "crm_deal", deal_doc.name)
			return {"name": existing_from_lead, "created": False}

	bid = frappe.new_doc("Bid")
	bid.client_account = deal_doc.organization or deal_doc.lead_name or deal_doc.name
	bid.crm_deal = deal_doc.name
	bid.bd_owner = frappe.session.user
	# CRM Deal's own "source" is a freeform CRM Lead Source Link with no
	# fixed values, so it can't be mapped onto Bid's fixed Select options
	# reliably — "Other" is an honest placeholder rather than a guess.
	bid.source = "Other"
	if deal_doc.deal_value:
		bid.bid_value = deal_doc.deal_value
	if deal_doc.currency:
		bid.currency = deal_doc.currency
	bid.insert()

	return {"name": bid.name, "created": True}


def create_bid_from_lead(lead):
	"""Create a Bid pre-filled from a CRM Lead.

	Called by on_lead_status_change below, the moment a Lead reaches
	"Qualified" — including via a plain kanban drag, which only changes
	the Lead's status and does not go through "Convert to Deal" (that's
	a separate, explicit action), so no CRM Deal exists yet at this
	point. Idempotent on Bid.crm_lead for the same reason
	create_bid_from_deal is idempotent on crm_deal: nothing stops a Lead
	being dragged back out of Qualified and in again.
	"""
	existing = frappe.db.get_value("Bid", {"crm_lead": lead}, "name")
	if existing:
		return {"name": existing, "created": False}

	lead_doc = frappe.get_doc("CRM Lead", lead)

	bid = frappe.new_doc("Bid")
	bid.client_account = lead_doc.organization or lead_doc.lead_name or lead_doc.name
	bid.crm_lead = lead_doc.name
	bid.bd_owner = frappe.session.user
	# Same reasoning as create_bid_from_deal: CRM's own source field is a
	# freeform Link with no fixed values, so it can't be mapped reliably.
	bid.source = "Other"
	bid.insert(ignore_permissions=True)

	return {"name": bid.name, "created": True}


def on_lead_status_change(doc, method=None):
	"""doc_events hook: CRM Lead on_update.

	Fires on every Lead save, including a plain kanban drag (which saves
	via frappe.client.set_value — a normal document save that runs this
	hook — unlike the "Convert to Deal" button, which sets status via
	db_set() and bypasses on_update entirely). Only acts the moment
	status actually changes to "Qualified", not on every unrelated save.

	Wrapped so a failure here can never block the Lead's own save —
	same defensive stance as the escalation jobs in tasks.py never
	blocking the Bid they're checking.
	"""
	if not (doc.has_value_changed("status") and doc.status == "Qualified"):
		return
	try:
		create_bid_from_lead(doc.name)
	except Exception:
		frappe.log_error(title="Auto Bid creation from Lead failed")
