# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

# Proposal links to Bid, which itself has optional Customer/CRM Deal Link
# fields — same reasoning as test_bid.py: skip IntegrationTestCase's
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


class TestProposal(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		frappe.local.test_objects.setdefault("Proposal", [])
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

	def make_proposal(self, bid_name, **kwargs):
		doc = frappe.get_doc(
			{
				"doctype": "Proposal",
				"bid": bid_name,
				"proposal_template": "General",
				**kwargs,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	def make_output(self, bid_name, workstream, **kwargs):
		doc = frappe.get_doc(
			{
				"doctype": "Bid Workstream Output",
				"bid": bid_name,
				"workstream": workstream,
				**kwargs,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	def test_workstream_lead_cannot_write_proposal(self):
		bid = self.make_bid(technical_lead="tech@bidtest.com")
		proposal = self.make_proposal(bid.name)

		frappe.set_user("tech@bidtest.com")
		d = frappe.get_doc("Proposal", proposal.name)
		d.technical_approach = "Trying to edit directly"
		with self.assertRaises(frappe.PermissionError):
			d.save()

	def test_bid_manager_can_write_proposal(self):
		bid = self.make_bid(bid_manager="bidmgr@bidtest.com")
		proposal = self.make_proposal(bid.name)

		frappe.set_user("bidmgr@bidtest.com")
		d = frappe.get_doc("Proposal", proposal.name)
		d.executive_summary = "Written by the Bid Manager"
		d.save()  # should not raise
		self.assertEqual(
			frappe.get_cached_doc("Proposal", proposal.name).executive_summary,
			"Written by the Bid Manager",
		)

	def test_pull_requires_bid_manager(self):
		bid = self.make_bid(bid_manager="bidmgr@bidtest.com")
		proposal = self.make_proposal(bid.name)
		self.make_output(bid.name, "Technical", content="Technical write-up", ready_for_proposal=1)

		# Sales has doctype-level write on Proposal, but pulling is
		# specifically the Bid Manager's call — should still be blocked.
		frappe.set_user("sales@bidtest.com")
		d = frappe.get_doc("Proposal", proposal.name)
		with self.assertRaises(frappe.ValidationError):
			d.pull_workstream_outputs()

	def test_pull_copies_ready_content_into_empty_sections_only(self):
		bid = self.make_bid(bid_manager="bidmgr@bidtest.com")
		proposal = self.make_proposal(bid.name, commercial_terms="Already drafted pricing narrative")
		self.make_output(bid.name, "Technical", content="Technical write-up", ready_for_proposal=1)
		self.make_output(bid.name, "Financial", content="Financial write-up", ready_for_proposal=1)
		self.make_output(bid.name, "Administrative", content="")  # not ready

		frappe.set_user("bidmgr@bidtest.com")
		d = frappe.get_doc("Proposal", proposal.name)
		result = d.pull_workstream_outputs()

		self.assertEqual(sorted(result["pulled"]), ["Technical"])
		self.assertEqual(result["skipped_has_content"], ["Financial"])
		self.assertEqual(result["skipped_not_ready"], ["Administrative"])

		saved = frappe.get_cached_doc("Proposal", proposal.name)
		self.assertEqual(saved.technical_approach, "Technical write-up")
		# Pre-existing content must survive untouched, not be overwritten
		# by the ready Financial output.
		self.assertEqual(saved.commercial_terms, "Already drafted pricing narrative")
		self.assertFalse(saved.compliance_statement)
		# No workstream maps to Executive Summary — the Bid Manager's own
		# synthesis, never auto-filled.
		self.assertFalse(saved.executive_summary)

	def test_pull_does_not_modify_the_source_workstream_output(self):
		bid = self.make_bid(bid_manager="bidmgr@bidtest.com")
		proposal = self.make_proposal(bid.name)
		output = self.make_output(bid.name, "Technical", content="Original write-up", ready_for_proposal=1)

		frappe.set_user("bidmgr@bidtest.com")
		frappe.get_doc("Proposal", proposal.name).pull_workstream_outputs()

		self.assertEqual(
			frappe.get_cached_doc("Bid Workstream Output", output.name).content, "Original write-up"
		)

	def test_editing_workstream_output_after_pull_does_not_touch_proposal(self):
		bid = self.make_bid(bid_manager="bidmgr@bidtest.com", technical_lead="tech@bidtest.com")
		proposal = self.make_proposal(bid.name)
		output = self.make_output(bid.name, "Technical", content="Version 1", ready_for_proposal=1)

		frappe.set_user("bidmgr@bidtest.com")
		frappe.get_doc("Proposal", proposal.name).pull_workstream_outputs()
		self.assertEqual(frappe.get_cached_doc("Proposal", proposal.name).technical_approach, "Version 1")

		frappe.set_user("tech@bidtest.com")
		d = frappe.get_doc("Bid Workstream Output", output.name)
		d.content = "Version 2 — revised after the pull"
		d.save()

		# The already-built Proposal must not have silently changed.
		self.assertEqual(frappe.get_cached_doc("Proposal", proposal.name).technical_approach, "Version 1")
