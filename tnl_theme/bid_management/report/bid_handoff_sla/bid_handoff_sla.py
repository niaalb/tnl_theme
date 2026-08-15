# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns = [
		{"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 100},
		{"fieldname": "handoffs", "label": _("Hand-offs"), "fieldtype": "Int", "width": 100},
		{
			"fieldname": "avg_ack_seconds",
			"label": _("Avg. Time to Acknowledge"),
			"fieldtype": "Duration",
			"width": 200,
		},
		{
			"fieldname": "pct_within_sla",
			"label": _("% Acknowledged Within 2 Business Days"),
			"fieldtype": "Percent",
			"width": 250,
		},
	]

	data = frappe.db.sql(
		"""
		SELECT
			DATE_FORMAT(handoff_date, '%Y-%m') AS month,
			COUNT(*) AS handoffs,
			AVG(TIMESTAMPDIFF(SECOND, handoff_date, handoff_acknowledged_on)) AS avg_ack_seconds,
			100 * SUM(DATE(handoff_acknowledged_on) <= handoff_escalation_due) / COUNT(*) AS pct_within_sla
		FROM `tabBid`
		WHERE handoff_date IS NOT NULL AND handoff_acknowledged_on IS NOT NULL
		GROUP BY month
		ORDER BY month DESC
		""",
		as_dict=True,
	)

	return columns, data
