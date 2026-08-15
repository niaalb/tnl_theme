# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns = [
		{"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 100},
		{"fieldname": "identified", "label": _("Identified"), "fieldtype": "Int", "width": 100},
		{"fieldname": "qualified", "label": _("Qualified"), "fieldtype": "Int", "width": 100},
		{"fieldname": "bidding", "label": _("Bidding"), "fieldtype": "Int", "width": 100},
		{"fieldname": "won", "label": _("Won"), "fieldtype": "Int", "width": 100},
	]

	data = frappe.db.sql(
		"""
		SELECT
			DATE_FORMAT(creation, '%Y-%m') AS month,
			SUM(stage = 'Identified') AS identified,
			SUM(stage IN ('Handed Off', 'Qualifying')) AS qualified,
			SUM(stage IN ('Kickoff', 'In Progress', 'Submitted')) AS bidding,
			SUM(outcome = 'Won') AS won
		FROM `tabBid`
		GROUP BY month
		ORDER BY month DESC
		""",
		as_dict=True,
	)

	return columns, data
