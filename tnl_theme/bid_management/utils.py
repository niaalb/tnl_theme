from frappe.utils import add_days, getdate


def add_business_days(base_date, n_days):
	"""Add n_days business days (Mon-Fri) to base_date, skipping weekends.

	Deliberately simple — doesn't consult a Holiday List. The client's
	escalation rule is "2 business days," which in practice means "skip
	Saturday/Sunday"; company-specific public holidays weren't part of the
	stated requirement, so this isn't over-built for a case that wasn't
	asked for."""
	d = getdate(base_date)
	added = 0
	while added < n_days:
		d = add_days(d, 1)
		if d.weekday() < 5:  # Monday=0 ... Sunday=6
			added += 1
	return d
