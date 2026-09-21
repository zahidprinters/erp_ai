# ---------------------------------------------------------------------------
# Field validators — check user input for correctness.
#
# Single responsibility: given a field name and raw user input, decide if
# it's valid and convert it to the right type. No ERP operations.
# ---------------------------------------------------------------------------
from typing import Any, Optional, Tuple

# Fields that must parse as numbers
NUMERIC_FIELDS = frozenset(
	{
		"qty",
		"rate",
		"price",
		"amount",
		"paid_amount",
		"received_amount",
		"total_debit",
		"total_credit",
		"discount_percent",
		"standard_rate",
		"opening_stock",
		"min_amount",
		"max_amount",
		"valuation_rate",
		"rejected_qty",
		"debit_in_account_currency",
		"credit_in_account_currency",
		"basic_rate",
	}
)


def is_numeric(field: str) -> bool:
	"""True if the field must be a number."""
	return field in NUMERIC_FIELDS


def parse_number(raw: str) -> Optional[float]:
	"""Parse a number from user text. Handles '1,200', 'rs 500', '500pk', etc."""
	if raw is None:
		return None
	if isinstance(raw, (int, float)):
		return float(raw)
	s = str(raw).strip()
	# Remove common prefixes/suffixes
	s = s.lower().replace("rs", "").replace("rupees", "").replace("pkr", "")
	s = s.replace(",", "").replace("pcs", "").replace("nos", "").replace("kg", "").replace("pcs", "")
	s = s.strip()
	try:
		return float(s)
	except ValueError:
		return None


def validate_field(field: str, raw: str) -> Tuple[Any, Optional[str]]:
	"""Validate and convert a field value.

	Returns (converted_value, error_message). error_message None means OK.
	"""
	if is_numeric(field):
		n = parse_number(raw)
		if n is None:
			return (None, "Please enter a valid number for %s." % field.replace("_", " "))
		return (n, None)
	# String field — just strip
	s = str(raw).strip()
	if not s:
		return (None, "This field cannot be empty.")
	return (s, None)
