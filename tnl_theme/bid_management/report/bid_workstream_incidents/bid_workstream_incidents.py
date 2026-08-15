# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns = [
		{"fieldname": "workstream", "label": _("Workstream"), "fieldtype": "Data", "width": 150},
		{"fieldname": "late_incidents", "label": _("Late Incidents"), "fieldtype": "Int", "width": 150},
		{"fieldname": "rework_incidents", "label": _("Rework Incidents"), "fieldtype": "Int", "width": 150},
		{"fieldname": "total_checkpoints", "label": _("Total Checkpoints Logged"), "fieldtype": "Int", "width": 200},
	]

	data = frappe.db.sql(
		"""
		SELECT
			workstream,
			SUM(is_late) AS late_incidents,
			SUM(is_rework) AS rework_incidents,
			COUNT(*) AS total_checkpoints
		FROM `tabBid Workstream Update`
		GROUP BY workstream
		ORDER BY (SUM(is_late) + SUM(is_rework)) DESC
		""",
		as_dict=True,
	)

	return columns, data
