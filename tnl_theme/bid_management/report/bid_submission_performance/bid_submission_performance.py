# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns = [
		{"fieldname": "bid_manager", "label": _("Bid Manager"), "fieldtype": "Link", "options": "User", "width": 200},
		{"fieldname": "submissions", "label": _("Submissions"), "fieldtype": "Int", "width": 100},
		{"fieldname": "on_time", "label": _("On Time"), "fieldtype": "Int", "width": 100},
		{
			"fieldname": "pct_on_time",
			"label": _("% On-Time"),
			"fieldtype": "Percent",
			"width": 150,
		},
	]

	data = frappe.db.sql(
		"""
		SELECT
			bid_manager,
			COUNT(*) AS submissions,
			SUM(submission_date <= submission_deadline) AS on_time,
			100 * SUM(submission_date <= submission_deadline) / COUNT(*) AS pct_on_time
		FROM `tabBid`
		WHERE submission_date IS NOT NULL AND submission_deadline IS NOT NULL
		GROUP BY bid_manager
		ORDER BY pct_on_time DESC
		""",
		as_dict=True,
	)

	return columns, data
