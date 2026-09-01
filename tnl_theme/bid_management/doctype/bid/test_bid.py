# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from crm.fcrm.doctype.crm_lead.crm_lead import convert_to_deal
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from tnl_theme.bid_management import api, tasks
from tnl_theme.bid_management.utils import add_business_days

# Bid's `customer`/`crm_deal` Link fields are optional and never
# populated in these tests, but IntegrationTestCase auto-generates test
# fixtures for every Link field by default — pulling in Customer's and
# CRM Deal's own dependency chains, which is unnecessary overhead here
# and can collide with real data on a non-throwaway site.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Customer", "CRM Deal"]

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

		# convert_to_deal() itself only conditionally db_sets status to
		# "Qualified" if this status record exists (see crm_lead.py) — a
		# throwaway/CI site may not have either of these statuses seeded,
		# so create them rather than assume.
		for lead_status in ("New", "Qualified"):
			if not frappe.db.exists("CRM Lead Status", lead_status):
				frappe.get_doc(
					{"doctype": "CRM Lead Status", "name": lead_status, "lead_status": lead_status}
				).insert(ignore_permissions=True)

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

	def make_lead(self, **kwargs):
		doc = frappe.get_doc(
			{
				"doctype": "CRM Lead",
				"first_name": "Test",
				"last_name": "Lead",
				"status": "New",
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

	def _bid_ready_for_kickoff(self):
		"""Drives a fresh Bid through Hand Off -> Acknowledge -> Mark as Go
		— the setup portion of test_full_workflow_walkthrough, stopping
		just short of confirming Kickoff itself, so callers can test that
		one transition's side effects in isolation."""
		frappe.set_user("bd@bidtest.com")
		bid = self.make_bid()

		d = frappe.get_doc("Bid", bid.name)
		d.sales_owner = "sales@bidtest.com"
		d.save()
		apply_workflow(frappe.get_doc("Bid", bid.name), "Hand Off to Sales")

		frappe.set_user("sales@bidtest.com")
		apply_workflow(frappe.get_doc("Bid", bid.name), "Acknowledge Receipt")

		d = frappe.get_doc("Bid", bid.name)
		d.bid_no_bid_decision = "Bid"
		d.qualification_reasoning = "Good fit"
		d.save()
		apply_workflow(frappe.get_doc("Bid", bid.name), "Mark as Go")

		return bid.name

	def _confirm_kickoff(self, bid_name):
		frappe.set_user("bidmgr@bidtest.com")
		d = frappe.get_doc("Bid", bid_name)
		d.technical_lead = "tech@bidtest.com"
		d.financial_lead = "fin@bidtest.com"
		d.administrative_lead = "admin@bidtest.com"
		d.submission_deadline = add_days(today(), 10)
		d.save()
		apply_workflow(frappe.get_doc("Bid", bid_name), "Confirm Kickoff & Assign Leads")

	def test_kickoff_transition_auto_creates_workstream_outputs(self):
		bid_name = self._bid_ready_for_kickoff()
		self._confirm_kickoff(bid_name)

		outputs = frappe.get_all(
			"Bid Workstream Output", filters={"bid": bid_name}, fields=["workstream", "ready_for_proposal"]
		)
		self.assertEqual(len(outputs), 3)
		self.assertEqual({o.workstream for o in outputs}, {"Technical", "Financial", "Administrative"})
		self.assertTrue(all(o.ready_for_proposal == 0 for o in outputs))

	def test_kickoff_transition_is_idempotent_for_outputs(self):
		bid_name = self._bid_ready_for_kickoff()
		self._confirm_kickoff(bid_name)

		# Save again while already In Progress — stage unchanged, so the
		# hook should no-op rather than raising on the duplicate-row check.
		d = frappe.get_doc("Bid", bid_name)
		d.next_action = "Follow up with Technical Lead"
		d.save()

		self.assertEqual(frappe.db.count("Bid Workstream Output", {"bid": bid_name}), 3)

	def test_kanban_qualify_creates_a_bid(self):
		"""Acceptance scenario 1: Lead -> Qualified via a normal save (what
		a kanban drag does) must still auto-create a linked Bid — the
		on_deal_after_insert hook added for scenario 2 must not have
		disturbed this existing path."""
		lead = self.make_lead(first_name="Kanban")
		lead.status = "Qualified"
		lead.save(ignore_permissions=True)

		bid_name = frappe.db.get_value("Bid", {"crm_lead": lead.name}, "name")
		self.assertIsNotNone(bid_name, "qualifying a Lead should auto-create a Bid")
		bid = frappe.get_doc("Bid", bid_name)
		self.assertEqual(bid.crm_lead, lead.name)
		self.assertIsNone(bid.crm_deal)  # no Deal exists yet at this point

	def test_convert_to_deal_creates_a_bid(self):
		"""Acceptance scenario 2: the standard "Convert to Deal" button
		path. convert_to_deal() advances the Lead's status via db_set(),
		which bypasses on_update — this is the exact path the fix targets."""
		lead = self.make_lead(first_name="Convert")

		deal_name = convert_to_deal(lead=lead.name, doc=lead)

		bid_name = frappe.db.get_value("Bid", {"crm_deal": deal_name}, "name")
		self.assertIsNotNone(bid_name, "converting a Lead to a Deal should auto-create a linked Bid")
		bid = frappe.get_doc("Bid", bid_name)
		self.assertEqual(bid.crm_deal, deal_name)
		self.assertEqual(bid.crm_lead, lead.name, "the Bid should carry the originating Lead too")

	def test_convert_to_deal_after_kanban_qualify_reuses_same_bid(self):
		"""Acceptance scenario 3 (first form): a Lead qualified via kanban
		(creating a Bid via crm_lead) that is later also converted to a
		Deal must link that SAME Bid, not create a second one."""
		lead = self.make_lead(first_name="BothPaths")
		lead.status = "Qualified"
		lead.save(ignore_permissions=True)
		bid_from_kanban = frappe.db.get_value("Bid", {"crm_lead": lead.name}, "name")
		self.assertIsNotNone(bid_from_kanban)

		lead.reload()
		deal_name = convert_to_deal(lead=lead.name, doc=lead)

		bids_for_lead = frappe.get_all("Bid", filters={"crm_lead": lead.name})
		self.assertEqual(len(bids_for_lead), 1, "must not create a second Bid for the same Lead")
		self.assertEqual(bids_for_lead[0].name, bid_from_kanban)
		self.assertEqual(frappe.db.get_value("Bid", bid_from_kanban, "crm_deal"), deal_name)

	def test_create_bid_from_deal_button_stays_idempotent_after_hook(self):
		"""Acceptance scenarios 3 (second form) and 4: after on_deal_after_insert
		has already auto-created a Bid for a converted Deal, the pre-existing
		manual "Create Bid" button (create_bid_from_deal) must still work
		exactly as before — finding the existing Bid, not duplicating it."""
		lead = self.make_lead(first_name="ManualButton")
		deal_name = convert_to_deal(lead=lead.name, doc=lead)

		frappe.set_user("bd@bidtest.com")
		result = api.create_bid_from_deal(deal_name)
		self.assertFalse(result["created"], "the hook already created one; the button must reuse it")

		bids_for_deal = frappe.get_all("Bid", filters={"crm_deal": deal_name})
		self.assertEqual(len(bids_for_deal), 1, "only one Bid should exist for this Deal")
