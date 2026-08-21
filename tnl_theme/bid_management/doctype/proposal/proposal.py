# Copyright (c) 2026, TNL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Proposal(Document):
	def before_insert(self):
		existing_count = frappe.db.count("Proposal", {"bid": self.bid})
		self.version = existing_count + 1

		# Frappe auto-fills any field literally named "letter_head" from a
		# site-wide sticky default (tabDefaultValue) before this hook runs,
		# so `self.letter_head` is never actually empty here — an emptiness
		# check would always lose to that generic default. The template's
		# own default has to win outright; users can still edit the field
		# by hand after the Proposal is created.
		if self.proposal_template:
			template_default = frappe.db.get_value(
				"Proposal Template", self.proposal_template, "default_letter_head"
			)
			if template_default:
				self.letter_head = template_default

	def on_update(self):
		if self.status != "Sent":
			return
		# At most one "live" sent proposal per Bid — anything else that
		# was Final for the same Bid is now superseded by this one.
		frappe.db.set_value(
			"Proposal",
			{"bid": self.bid, "status": "Final", "name": ["!=", self.name]},
			"status",
			"Superseded",
		)
