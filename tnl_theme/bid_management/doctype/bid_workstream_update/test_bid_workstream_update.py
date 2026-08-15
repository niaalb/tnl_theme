# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

# Most of this child table's real behavior (ownership enforcement, the
# workstream-incidents KPI report reading is_late/is_rework) is exercised
# via the parent Bid's own tests — this covers just the row shape itself.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Customer", "Opportunity"]


class TestBidWorkstreamUpdate(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		frappe.local.test_objects.setdefault("Bid Workstream Update", [])
		super().setUpClass()

	def test_checkpoint_row_appends_to_bid(self):
		bid = frappe.get_doc(
			{
				"doctype": "Bid",
				"client_account": "Checkpoint Test Client",
				"source": "RFP",
				"bd_owner": "Administrator",
			}
		)
		bid.append(
			"workstream_updates",
			{
				"workstream": "Technical",
				"status": "In Progress",
				"remarks": "Kicked off discovery",
			},
		)
		bid.insert(ignore_permissions=True)

		self.assertEqual(len(bid.workstream_updates), 1)
		row = bid.workstream_updates[0]
		self.assertEqual(row.workstream, "Technical")
		self.assertEqual(row.status, "In Progress")
		self.assertEqual(row.updated_by, "Administrator")
