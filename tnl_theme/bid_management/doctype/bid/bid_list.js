frappe.listview_settings["Bid"] = {
	add_fields: [
		"stage",
		"outcome",
		"handoff_escalated",
		"escalated_technical",
		"escalated_financial",
		"escalated_administrative",
	],

	get_indicator(doc) {
		if (doc.handoff_escalated || doc.escalated_technical || doc.escalated_financial || doc.escalated_administrative) {
			return [__("Escalated"), "red", "stage,=," + doc.stage];
		}

		if (doc.stage === "Closed") {
			if (doc.outcome === "Won") return [__("Won"), "green", "outcome,=,Won"];
			if (doc.outcome === "Lost") return [__("Lost"), "red", "outcome,=,Lost"];
			if (doc.outcome === "On Hold") return [__("On Hold"), "orange", "outcome,=,On Hold"];
			return [__("Closed"), "gray", "stage,=,Closed"];
		}

		const stage_colors = {
			Identified: "gray",
			"Handed Off": "orange",
			Qualifying: "yellow",
			Kickoff: "blue",
			"In Progress": "blue",
			Submitted: "purple",
		};

		return [__(doc.stage), stage_colors[doc.stage] || "gray", "stage,=," + doc.stage];
	},
};
