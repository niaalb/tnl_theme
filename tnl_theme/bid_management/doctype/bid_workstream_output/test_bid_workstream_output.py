# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.file_manager import save_file

# Bid Workstream Output links to Bid, which itself has optional Customer/CRM
# Deal Link fields — same reasoning as test_bid.py: skip IntegrationTestCase's
# automatic test-record generation for those rather than pull in their full
# dependency chains.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Customer", "CRM Deal"]

TEST_USERS = {
	"bd@bidtest.com": "Business Development",
	"sales@bidtest.com": "Sales",
	"bidmgr@bidtest.com": "Bid Manager",
	"tech@bidtest.com": "Technical Lead",
	"fin@bidtest.com": "Financial Lead",
	"admin@bidtest.com": "Administrative Lead",
}


class TestBidWorkstreamOutput(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		frappe.local.test_objects.setdefault("Bid Workstream Output", [])
		super().setUpClass()
		for email, role in TEST_USERS.items():
			if not frappe.db.exists("User", email):
				user = frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": email.split("@")[0],
						"send_welcome_email": 0,
					}
				)
				user.append("roles", {"role": role})
				user.insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")

	def make_bid(self, **kwargs):
		doc = frappe.get_doc(
			{
				"doctype": "Bid",
				"client_account": "Test Client",
				"source": "RFP",
				"bd_owner": "bd@bidtest.com",
				**kwargs,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	def test_content_and_attachment_save(self):
		bid = self.make_bid()
		output = frappe.get_doc(
			{
				"doctype": "Bid Workstream Output",
				"bid": bid.name,
				"workstream": "Technical",
				"content": "Proposed architecture and delivery approach.",
			}
		)
		output.insert()

		save_file("spec.txt", b"dummy supporting document contents", "Bid Workstream Output", output.name, is_private=1)

		files = frappe.get_all("File", filters={"attached_to_name": output.name})
		self.assertEqual(len(files), 1)

	def test_one_row_per_workstream_enforced(self):
		bid = self.make_bid()
		frappe.get_doc({"doctype": "Bid Workstream Output", "bid": bid.name, "workstream": "Technical"}).insert()

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{"doctype": "Bid Workstream Output", "bid": bid.name, "workstream": "Technical"}
			).insert()

	def test_bid_and_workstream_immutable_after_creation(self):
		bid = self.make_bid()
		other_bid = self.make_bid()
		output = frappe.get_doc({"doctype": "Bid Workstream Output", "bid": bid.name, "workstream": "Technical"})
		output.insert()

		output.workstream = "Financial"
		with self.assertRaises(frappe.ValidationError):
			output.save()

		output.reload()
		output.bid = other_bid.name
		with self.assertRaises(frappe.ValidationError):
			output.save()

	def test_ownership_enforced_on_update(self):
		bid = self.make_bid(technical_lead="tech@bidtest.com", financial_lead="fin@bidtest.com")
		output = frappe.get_doc({"doctype": "Bid Workstream Output", "bid": bid.name, "workstream": "Technical"})
		output.insert()  # as Administrator — bypasses the ownership check by design

		frappe.set_user("fin@bidtest.com")  # Financial Lead on this Bid, not Technical Lead, not Bid Manager
		d = frappe.get_doc("Bid Workstream Output", output.name)
		d.content = "Not my workstream"
		with self.assertRaises(frappe.ValidationError):
			d.save()

		frappe.set_user("tech@bidtest.com")
		d = frappe.get_doc("Bid Workstream Output", output.name)
		d.content = "My workstream"
		d.save()  # should not raise
		self.assertEqual(
			frappe.get_cached_doc("Bid Workstream Output", output.name).content, "My workstream"
		)

	def test_ownership_enforced_on_insert(self):
		bid = self.make_bid(technical_lead="tech@bidtest.com", financial_lead="fin@bidtest.com")

		frappe.set_user("fin@bidtest.com")  # Financial Lead, not Technical Lead, not Bid Manager
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{"doctype": "Bid Workstream Output", "bid": bid.name, "workstream": "Technical"}
			).insert()

	def test_bid_manager_bypasses_ownership_check(self):
		bid = self.make_bid(bid_manager="bidmgr@bidtest.com", technical_lead="tech@bidtest.com")

		frappe.set_user("bidmgr@bidtest.com")
		output = frappe.get_doc(
			{
				"doctype": "Bid Workstream Output",
				"bid": bid.name,
				"workstream": "Technical",
				"content": "Drafted by the Bid Manager directly",
			}
		)
		output.insert()  # should not raise, even though bidmgr isn't the Technical Lead
		self.assertEqual(output.content, "Drafted by the Bid Manager directly")

	def test_ready_for_proposal_requires_content(self):
		bid = self.make_bid()
		output = frappe.get_doc({"doctype": "Bid Workstream Output", "bid": bid.name, "workstream": "Technical"})
		output.insert()

		output.ready_for_proposal = 1
		with self.assertRaises(frappe.ValidationError):
			output.save()

		output.reload()
		output.content = "Now there's content"
		output.ready_for_proposal = 1
		output.save()  # should not raise

	def test_ready_for_proposal_rejects_quill_empty_paragraph(self):
		"""Quill's own "empty" state is `<p><br></p>`, not an empty string
		— a plain truthiness check on content would wrongly treat this as
		meaningful content. Only actual typed text should count."""
		bid = self.make_bid()
		output = frappe.get_doc(
			{
				"doctype": "Bid Workstream Output",
				"bid": bid.name,
				"workstream": "Technical",
				"content": "<p><br></p>",
			}
		)
		output.insert()

		output.ready_for_proposal = 1
		with self.assertRaises(frappe.ValidationError):
			output.save()

	def test_content_supports_rich_structured_html(self):
		"""Confirms the field round-trips genuinely structured document
		content — headings, lists, a table — not just plain text, proving
		this is a real document-authoring field, not a note box."""
		bid = self.make_bid()
		rich_content = (
			"<h2>Approach</h2>"
			"<p>Overview paragraph with a <strong>bold</strong> phrase.</p>"
			"<ul><li>Point one</li><li>Point two</li></ul>"
			'<table class="table table-bordered"><tbody>'
			"<tr><td>Item</td><td>Cost</td></tr>"
			"<tr><td>Server</td><td>1000</td></tr>"
			"</tbody></table>"
		)
		output = frappe.get_doc(
			{
				"doctype": "Bid Workstream Output",
				"bid": bid.name,
				"workstream": "Technical",
				"content": rich_content,
			}
		)
		output.insert()

		saved = frappe.get_cached_doc("Bid Workstream Output", output.name)
		self.assertIn("<h2>Approach</h2>", saved.content)
		self.assertIn("<li>Point one</li>", saved.content)
		self.assertIn("<table", saved.content)
		self.assertIn("<tr><td>Server</td><td>1000</td></tr>", saved.content)

	def test_ready_for_proposal_stamps_and_clears_ready_on(self):
		bid = self.make_bid()
		output = frappe.get_doc(
			{
				"doctype": "Bid Workstream Output",
				"bid": bid.name,
				"workstream": "Technical",
				"content": "Draft content",
			}
		)
		output.insert()
		self.assertIsNone(output.ready_on)

		output.ready_for_proposal = 1
		output.save()
		self.assertIsNotNone(frappe.get_cached_doc("Bid Workstream Output", output.name).ready_on)

		output.reload()
		output.ready_for_proposal = 0
		output.save()
		self.assertIsNone(frappe.get_cached_doc("Bid Workstream Output", output.name).ready_on)

	def test_manual_create_fallback_when_hook_did_not_run(self):
		bid = self.make_bid(
			technical_lead="tech@bidtest.com",
			financial_lead="fin@bidtest.com",
			administrative_lead="admin@bidtest.com",
		)
		# Simulate the stage reaching In Progress via a direct column write
		# rather than a normal save — mirroring the exact kind of on_update
		# bypass the CRM Deal conversion fix (previous session) addressed —
		# so Bid's own Kickoff auto-creation hook never fires.
		frappe.db.set_value("Bid", bid.name, "stage", "In Progress")
		self.assertEqual(frappe.get_all("Bid Workstream Output", filters={"bid": bid.name}), [])

		frappe.set_user("tech@bidtest.com")
		output = frappe.get_doc({"doctype": "Bid Workstream Output", "bid": bid.name, "workstream": "Technical"})
		output.insert()  # the self-serve fallback — should succeed
		self.assertTrue(frappe.db.exists("Bid Workstream Output", output.name))
