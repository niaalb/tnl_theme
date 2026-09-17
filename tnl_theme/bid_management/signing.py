"""Self-hosted e-signature flow for Proposal — no third-party provider.

Kept as its own module, separate from proposal.py's controller logic,
mirroring how frappe_whatsapp isolates its own webhook.py rather than
mixing guest-facing code into doctype controllers. Every entrypoint here
is reached by a Guest with no session, so authorization is a Document
Share Key check (the same mechanism Frappe's own guest print/PDF links
use) rather than the doctype permission system, and every write uses
ignore_permissions=True.
"""

import frappe
from frappe import _
from frappe.utils import format_datetime

from tnl_theme.bid_management import signature_placement


def validate_key(proposal_name, key):
	"""Replicates the expiry check frappe.www.printview.validate_key does
	for guest print access — that function is internal to frappe core, so
	the same few lines are reimplemented here rather than imported. Two
	separate calls (exists, then get_value) rather than one, so "no
	matching key" and "key exists with no expiry set" (expires_on itself
	None) are never ambiguous with each other."""
	if not key:
		return False
	filters = {"reference_doctype": "Proposal", "reference_docname": proposal_name, "key": key}
	if not frappe.db.exists("Document Share Key", filters):
		return False
	expires_on = frappe.db.get_value("Document Share Key", filters, "expires_on")
	if expires_on and expires_on < frappe.utils.getdate():
		return False
	return True


def record_event(doc, event, signer_name=None, signer_email=None):
	"""Appends one signing_log row onto an already-loaded Proposal doc.
	Doesn't save — callers that are also changing other fields (see
	submit_signature/decline_signature) fold this into their own single
	save rather than triggering two."""
	doc.append(
		"signing_log",
		{
			"event": event,
			"signer_name": signer_name,
			"signer_email": signer_email,
			"ip_address": frappe.local.request_ip,
		},
	)


def record_view(proposal_name):
	"""Best-effort "Viewed" entry for the guest signing page's own GET —
	wrapped so a logging failure can never block the page from rendering,
	same defensive stance as tasks.py's escalation jobs.

	Frappe rolls back any database write made during a GET request unless
	frappe.local.flags.commit is explicitly set — GET requests aren't
	supposed to have side effects by default — so without this flag the
	log row would be silently discarded the moment the page finished
	rendering."""
	try:
		doc = frappe.get_doc("Proposal", proposal_name)
		record_event(doc, "Viewed")
		doc.save(ignore_permissions=True)
		frappe.local.flags.commit = True
	except Exception:
		frappe.log_error(title=f"Proposal view logging failed: {proposal_name}")


def _notify_bid_manager(doc, subject, message):
	"""Best-effort — the client's own sign/decline action must succeed
	regardless of whether this notification goes out. Deliberately no
	now=True: that flag doesn't send synchronously despite its name — it
	registers the send on frappe.db.after_commit, which runs outside
	this function's own try/except entirely, so a delivery failure would
	surface later, uncaught, right when the client's request is
	otherwise trying to finish successfully. Queuing normally (the same
	choice already made for send_for_signature's own email) keeps
	delivery fully decoupled from this request."""
	bid_manager = frappe.db.get_value("Bid", doc.bid, "bid_manager")
	if not bid_manager:
		return
	try:
		frappe.sendmail(recipients=[bid_manager], subject=subject, message=message)
	except Exception:
		frappe.log_error(title=f"Proposal signing notification failed: {doc.name}")


@frappe.whitelist(allow_guest=True)
def submit_signature(proposal, key, signer_name, signer_email, signature_data):
	"""Records the client's signature, appends a Signed log entry, and
	composites it into the actual rendered document at exactly the
	page/position "Place Signature" put it — a post-render pypdf merge
	(signature_placement.compose_signed_pdf), not baked into the print
	format's own Jinja."""
	if not validate_key(proposal, key):
		frappe.throw(_("This signing link is invalid or has expired."), frappe.PermissionError)

	doc = frappe.get_doc("Proposal", proposal)
	if doc.signature_status == "Signed":
		frappe.throw(_("This proposal has already been signed."))

	doc.signed_by_name = signer_name
	doc.signed_by_email = signer_email
	doc.signed_on = frappe.utils.now_datetime()
	doc.client_signature = signature_data
	doc.signature_status = "Signed"
	record_event(doc, "Signed", signer_name, signer_email)
	doc.save(ignore_permissions=True)

	# frappe.get_print does its own internal read/print permission check
	# (frappe.www.printview.validate_print_permission) regardless of any
	# ignore_permissions used elsewhere in this flow — Guest has no
	# permission on Proposal at all, so generating the base document and
	# compositing the signature into it needs a brief elevation, same
	# trust level as every other write in this function.
	current_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		base_pdf = signature_placement.render_base_pdf(doc)
		field_values = {
			"Signature": doc.client_signature,
			"Date": format_datetime(doc.signed_on, "d MMM yyyy"),
			"Signed By Name": doc.signed_by_name,
		}
		pdf_bytes = signature_placement.compose_signed_pdf(base_pdf, doc.signature_layout, field_values)
	finally:
		frappe.set_user(current_user)
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{doc.name}-signed.pdf",
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"attached_to_field": "signed_document",
			"content": pdf_bytes,
			"is_private": 1,
		}
	)
	file_doc.insert(ignore_permissions=True)
	frappe.db.set_value("Proposal", doc.name, "signed_document", file_doc.file_url)

	_notify_bid_manager(
		doc,
		_("Signed: {0}").format(doc.title or doc.name),
		_("{0} has signed the proposal {1}.").format(signer_name, doc.title or doc.name),
	)

	return {"signature_status": "Signed"}


@frappe.whitelist(allow_guest=True)
def decline_signature(proposal, key, signer_name, reason=None):
	if not validate_key(proposal, key):
		frappe.throw(_("This signing link is invalid or has expired."), frappe.PermissionError)

	doc = frappe.get_doc("Proposal", proposal)
	if doc.signature_status == "Signed":
		frappe.throw(_("This proposal has already been signed."))

	doc.signature_status = "Declined"
	record_event(doc, "Declined", signer_name)
	doc.save(ignore_permissions=True)

	message = _("{0} declined to sign the proposal {1}.").format(signer_name, doc.title or doc.name)
	if reason:
		message += " " + _("Reason: {0}").format(reason)
	_notify_bid_manager(doc, _("Declined: {0}").format(doc.title or doc.name), message)

	return {"signature_status": "Declined"}
