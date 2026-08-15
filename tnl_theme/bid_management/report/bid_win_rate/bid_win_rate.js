// Copyright (c) 2026, TNL and contributors
// For license information, please see license.txt

frappe.query_reports["Bid Win Rate"] = {
	filters: [
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: ["Overall", "Technical Lead", "Financial Lead", "Administrative Lead"],
			default: "Overall",
			reqd: 1,
		},
	],
};
