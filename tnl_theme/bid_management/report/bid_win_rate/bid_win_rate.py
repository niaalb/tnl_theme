# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from frappe import _

GROUP_BY_FIELD = {
	"Technical Lead": "technical_lead",
	"Financial Lead": "financial_lead",
	"Administrative Lead": "administrative_lead",
}


def execute(filters=None):
	filters = filters or {}
	group_by = filters.get("group_by") or "Overall"

	if group_by == "Overall":
		columns = [
			{"fieldname": "label", "label": _("Overall"), "fieldtype": "Data", "width": 150},
			{"fieldname": "won", "label": _("Won"), "fieldtype": "Int", "width": 100},
			{"fieldname": "lost", "label": _("Lost"), "fieldtype": "Int", "width": 100},
			{"fieldname": "win_rate", "label": _("Win Rate"), "fieldtype": "Percent", "width": 120},
		]
		row = frappe.db.sql(
			"""
			SELECT
				SUM(outcome = 'Won') AS won,
				SUM(outcome = 'Lost') AS lost,
				100 * SUM(outcome = 'Won') / NULLIF(SUM(outcome IN ('Won', 'Lost')), 0) AS win_rate
			FROM `tabBid`
			""",
			as_dict=True,
		)
		row[0]["label"] = "All Bids"
		return columns, row

	field = GROUP_BY_FIELD[group_by]
	columns = [
		{"fieldname": field, "label": _(group_by), "fieldtype": "Link", "options": "User", "width": 200},
		{"fieldname": "won", "label": _("Won"), "fieldtype": "Int", "width": 100},
		{"fieldname": "lost", "label": _("Lost"), "fieldtype": "Int", "width": 100},
		{"fieldname": "win_rate", "label": _("Win Rate"), "fieldtype": "Percent", "width": 120},
	]
	data = frappe.db.sql(
		f"""
		SELECT
			{field},
			SUM(outcome = 'Won') AS won,
			SUM(outcome = 'Lost') AS lost,
			100 * SUM(outcome = 'Won') / NULLIF(SUM(outcome IN ('Won', 'Lost')), 0) AS win_rate
		FROM `tabBid`
		WHERE {field} IS NOT NULL
		GROUP BY {field}
		ORDER BY win_rate DESC
		""",
		as_dict=True,
	)
	return columns, data
