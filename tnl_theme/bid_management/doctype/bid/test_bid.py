# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from tnl_theme.bid_management import tasks
from tnl_theme.bid_management.utils import add_business_days

# Bid's `customer`/`crm_opportunity` Link fields are optional and never
# populated in these tests, but IntegrationTestCase auto-generates test
# fixtures for every Link field by default — pulling in Customer's and
# Opportunity's own dependency chains (down to Fiscal Year), which is
# unnecessary overhead here and can collide with real Fiscal Year data
# on a non-throwaway site.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Customer", "Opportunity"]

TEST_USERS = {
	"bd@bidtest.com": "Business Development",
	"sales@bidtest.com": "Sales",
	"bidmgr@bidtest.com": "Bid Manager",
	"tech@bidtest.com": "Technical Lead",
	"fin@bidtest.com": "Financial Lead",
	"admin@bidtest.com": "Administrative Lead",
}


class TestBid(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		# Skip IntegrationTestCase's automatic test-record generation for
		# every Link field on Bid (Customer, Opportunity, User, ...) — its
		# dependency walk reaches all the way to Fiscal Year, which can
		# collide with a real Fiscal Year already on a non-throwaway site.
		# These tests build all the data they need themselves below, so
		# nothing here is actually lost by skipping it.
		frappe.local.test_objects.setdefault("Bid", [])
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

	def test_qualification_reasoning_required(self):
		bid = self.make_bid()
		bid.bid_no_bid_decision = "Bid"
		with self.assertRaises(frappe.ValidationError):
			bid.save(ignore_permissions=True)

		# A failed save still leaves the in-memory `modified` timestamp
		# advanced (set before validate() runs), which would otherwise
		# make the retry below fail check_if_latest() against the
		# unchanged DB row — reload to get a clean, DB-synced copy first.
		bid.reload()
		bid.bid_no_bid_decision = "Bid"
		bid.qualification_reasoning = "Strong fit"
		bid.save(ignore_permissions=True)  # should not raise

	def test_outcome_reasoning_required(self):
		bid = self.make_bid()
		bid.outcome = "Won"
		with self.assertRaises(frappe.ValidationError):
			bid.save(ignore_permissions=True)

		bid.reload()
		bid.outcome = "Won"
		bid.outcome_reasoning = "Client confirmed"
		bid.save(ignore_permissions=True)  # should not raise

	def test_workstream_ownership_enforced(self):
		bid = self.make_bid(technical_lead="tech@bidtest.com")

		frappe.set_user("bidmgr@bidtest.com")  # not the assigned lead, not Bid Manager on this doc either
		d = frappe.get_doc("Bid", bid.name)
		d.technical_status = "In Progress"
		with self.assertRaises(frappe.ValidationError):
			d.save()

		frappe.set_user("tech@bidtest.com")
		d = frappe.get_doc("Bid", bid.name)
		d.technical_status = "In Progress"
		d.save()  # should not raise
		self.assertEqual(frappe.get_cached_doc("Bid", bid.name).technical_status, "In Progress")

	def test_full_workflow_walkthrough(self):
		frappe.set_user("bd@bidtest.com")
		bid = self.make_bid()

		with self.assertRaises(frappe.ValidationError):
			frappe.set_user("sales@bidtest.com")
			apply_workflow(frappe.get_doc("Bid", bid.name), "Hand Off to Sales")

		frappe.set_user("bd@bidtest.com")
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(frappe.get_doc("Bid", bid.name), "Hand Off to Sales")

		d = frappe.get_doc("Bid", bid.name)
		d.sales_owner = "sales@bidtest.com"
		d.save()
		apply_workflow(frappe.get_doc("Bid", bid.name), "Hand Off to Sales")
		self.assertEqual(frappe.get_cached_doc("Bid", bid.name).stage, "Handed Off")

		frappe.set_user("sales@bidtest.com")
		apply_workflow(frappe.get_doc("Bid", bid.name), "Acknowledge Receipt")
		self.assertEqual(frappe.get_cached_doc("Bid", bid.name).stage, "Qualifying")

		with self.assertRaises(frappe.ValidationError):
			apply_workflow(frappe.get_doc("Bid", bid.name), "Mark as Go")

		d = frappe.get_doc("Bid", bid.name)
		d.bid_no_bid_decision = "Bid"
		d.qualification_reasoning = "Good fit"
		d.save()
		apply_workflow(frappe.get_doc("Bid", bid.name), "Mark as Go")
		self.assertEqual(frappe.get_cached_doc("Bid", bid.name).stage, "Kickoff")

		frappe.set_user("bidmgr@bidtest.com")
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(frappe.get_doc("Bid", bid.name), "Confirm Kickoff & Assign Leads")

		d = frappe.get_doc("Bid", bid.name)
		d.technical_lead = "tech@bidtest.com"
		d.financial_lead = "fin@bidtest.com"
		d.administrative_lead = "admin@bidtest.com"
		d.submission_deadline = add_days(today(), 10)
		d.save()
		apply_workflow(frappe.get_doc("Bid", bid.name), "Confirm Kickoff & Assign Leads")
		self.assertEqual(frappe.get_cached_doc("Bid", bid.name).stage, "In Progress")

		for user, field in [
			("tech@bidtest.com", "technical_status"),
			("fin@bidtest.com", "financial_status"),
			("admin@bidtest.com", "administrative_status"),
		]:
			frappe.set_user(user)
			d = frappe.get_doc("Bid", bid.name)
			d.set(field, "Completed")
			d.save()

		frappe.set_user("bidmgr@bidtest.com")
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(frappe.get_doc("Bid", bid.name), "Submit Consolidated Package")

		d = frappe.get_doc("Bid", bid.name)
		d.consolidated_package_ready = 1
		d.submission_date = today()
		d.save()
		apply_workflow(frappe.get_doc("Bid", bid.name), "Submit Consolidated Package")
		self.assertEqual(frappe.get_cached_doc("Bid", bid.name).stage, "Submitted")

		frappe.set_user("sales@bidtest.com")
		d = frappe.get_doc("Bid", bid.name)
		d.outcome = "Won"
		d.outcome_reasoning = "Client confirmed award"
		d.save()
		apply_workflow(frappe.get_doc("Bid", bid.name), "Record Outcome")
		self.assertEqual(frappe.get_cached_doc("Bid", bid.name).stage, "Closed")

	def test_handoff_escalation_due_uses_business_days(self):
		bid = self.make_bid(sales_owner="sales@bidtest.com")
		apply_workflow(bid, "Hand Off to Sales")
		bid.reload()
		self.assertEqual(bid.handoff_escalation_due, add_business_days(bid.handoff_date, 2))

	def test_escalation_job_is_idempotent(self):
		sent = []
		original_sendmail = tasks.frappe.sendmail
		tasks.frappe.sendmail = lambda **kwargs: sent.append(kwargs)
		self.addCleanup(lambda: setattr(tasks.frappe, "sendmail", original_sendmail))

		bid = self.make_bid(sales_owner="sales@bidtest.com", bid_manager="bidmgr@bidtest.com")
		apply_workflow(bid, "Hand Off to Sales")
		frappe.db.set_value("Bid", bid.name, "handoff_escalation_due", add_days(today(), -1))

		tasks.check_bid_escalations()
		self.assertEqual(len(sent), 1)
		self.assertEqual(frappe.db.get_value("Bid", bid.name, "handoff_escalated"), 1)

		tasks.check_bid_escalations()
		self.assertEqual(len(sent), 1, "must not send a duplicate escalation on re-run")
