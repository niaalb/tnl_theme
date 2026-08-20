frappe.views.calendar["Bid"] = {
	field_map: {
		start: "submission_deadline",
		end: "submission_deadline",
		id: "name",
		title: "client_account",
		allDay: "allDay",
	},
	fields: ["stage", "outcome", "handoff_escalated", "escalated_technical", "escalated_financial", "escalated_administrative"],
	gantt: false,
	filters: [
		{
			fieldtype: "Select",
			fieldname: "stage",
			options: "Identified\nHanded Off\nQualifying\nKickoff\nIn Progress\nSubmitted\nClosed",
			label: __("Stage"),
		},
	],
	get_events_method: "frappe.desk.calendar.get_events",
	get_css_class: function (data) {
		if (data.stage === "Closed") {
			if (data.outcome === "Won") return "success";
			if (data.outcome === "Lost") return "danger";
			return "default";
		}
		if (
			data.handoff_escalated ||
			data.escalated_technical ||
			data.escalated_financial ||
			data.escalated_administrative
		) {
			return "danger";
		}
		return "warning";
	},
};
