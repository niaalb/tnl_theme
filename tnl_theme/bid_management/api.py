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
