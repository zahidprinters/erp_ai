# ---------------------------------------------------------------------------
# Core module tests — schema, intents, safety, validators, questions.
# These tests run without a Frappe DB connection (pure Python logic only).
# ---------------------------------------------------------------------------
from erp_ai.intents import detect_intent
from erp_ai.questions import get_hint, get_question
from erp_ai.safety import check_illegal_operation, get_duplication_fields
from erp_ai.schema import DOCTYPE_SCHEMAS, get_defaults, get_label, get_required_fields, get_schema
from erp_ai.validators import is_numeric, parse_number, validate_field


def test_schema_single_source():
	"""DOCTYPE_SCHEMAS must have entries for all core doctypes."""
	expected = {
		"Item",
		"Customer",
		"Supplier",
		"Sales Invoice",
		"Purchase Invoice",
		"Sales Order",
		"Purchase Order",
		"Payment Entry",
		"Delivery Note",
		"Purchase Receipt",
		"Stock Entry",
		"Journal Entry",
		"Material Request",
		"Quotation",
		"Warehouse",
		"Price List",
		"Lead",
	}
	assert expected.issubset(set(DOCTYPE_SCHEMAS.keys())), "Missing doctypes: %s" % (
		expected - set(DOCTYPE_SCHEMAS.keys())
	)


def test_schema_required_fields_present():
	"""Every schema entry must have a non-empty required list."""
	for doctype, schema in DOCTYPE_SCHEMAS.items():
		assert schema.get("required"), "%s has no required fields" % doctype


def test_get_schema_returns_dict():
	s = get_schema("Item")
	assert s is not None
	assert "required" in s
	assert "item_name" in s["required"]


def test_get_defaults_item():
	d = get_defaults("Item")
	assert d.get("item_group") == "Products"
	assert d.get("stock_uom") == "Nos"


def test_get_label_fallback():
	label = get_label("Item", "nonexistent_field")
	assert label == "Nonexistent Field"  # title-case fallback


def test_intent_detection_item():
	result = detect_intent("add new item steel rod")
	assert result is not None
	doctype, action = result
	assert doctype == "Item"
	assert action == "create"


def test_intent_detection_urdu():
	result = detect_intent("banao customer")
	assert result is not None
	assert result[0] == "Customer"


def test_intent_detection_none():
	result = detect_intent("hello how are you")
	assert result is None


def test_illegal_operation_blocked():
	err = check_illegal_operation("delete submitted invoice")
	assert err is not None
	assert "Cannot delete" in err


def test_illegal_operation_modify_submitted():
	err = check_illegal_operation("modify submitted document")
	assert err is not None


def test_legal_operation_passes():
	err = check_illegal_operation("create new customer")
	assert err is None


def test_duplication_fields():
	assert "item_name" in get_duplication_fields("Item")
	assert "customer_name" in get_duplication_fields("Customer")
	assert get_duplication_fields("Nonexistent") == []


def test_validate_numeric_field():
	val, err = validate_field("qty", "500")
	assert val == 500.0
	assert err is None


def test_validate_numeric_with_commas():
	val, err = validate_field("qty", "1,200")
	assert val == 1200.0


def test_validate_numeric_invalid():
	val, err = validate_field("qty", "abc")
	assert val is None
	assert err is not None


def test_validate_string_field():
	val, err = validate_field("item_name", "Steel Rod")
	assert val == "Steel Rod"
	assert err is None


def test_validate_empty_string():
	val, err = validate_field("item_name", "   ")
	assert val is None
	assert err is not None


def test_parse_number_with_currency():
	assert parse_number("rs 500") == 500.0
	assert parse_number("1,200 pkr") == 1200.0


def test_is_numeric():
	assert is_numeric("qty") is True
	assert is_numeric("rate") is True
	assert is_numeric("item_name") is False


def test_get_question_exists():
	q = get_question("Item", "item_name")
	assert q is not None
	assert len(q) > 0


def test_get_question_fallback():
	q = get_question("Item", "nonexistent")
	assert "nonexistent" in q.lower() or "provide" in q.lower()


def test_get_hint_exists():
	_ = get_hint("items")


# ---------------------------------------------------------------------------
# Affirmative / negative detectors (pure functions — no DB, no Frappe needed).
# These gate the auto-confirm-on-"yes" feature. Import from erp_ai.affirm which
# is a standalone pure-Python module.
# ---------------------------------------------------------------------------

from erp_ai.affirm import (
	_AFFIRMATIVE,
	NEGATIVE,
	_strip_yes_no_context,
	auto_confirm_reply,
	is_affirmative,
	is_negative,
)


def test_affirmative_token_set_non_empty():
	assert _AFFIRMATIVE
	for token in ("yes", "yeah", "yep", "sure", "go ahead"):
		assert token in _AFFIRMATIVE, "missing affirmative: %s" % token


def test_negative_token_set_non_empty():
	assert NEGATIVE
	for token in ("no", "nope", "nah", "not now", "cancel", "don't"):
		assert token in NEGATIVE, "missing negative: %s" % token


def test_is_affirmative_yes_family():
	for t in (
		"yes",
		"yeah",
		"yep",
		"yup",
		"y",
		"sure",
		"go ahead",
		"do it",
		"correct",
		"right",
		"create it",
		"make it",
	):
		assert is_affirmative(t) is True, t


def test_is_affirmative_with_light_punctuation():
	for t in ("yes,", "yeah!", "yep.", "sure?", "yes."):
		assert is_affirmative(t) is True, t


def test_is_affirmative_multiword():
	for t in (
		"go ahead",
		"go for it",
		"do it",
		"create it",
		"make it",
		"please do",
		"go ahead and create it",
	):
		assert is_affirmative(t) is True, t


def test_is_not_affirmative_hedged_or_negative():
	for t in (
		"maybe",
		"maybe later",
		"not sure",
		"no",
		"no thanks",
		"not now",
		"nah",
		"don't create it",
		"",
		"yes but",
		"yeah maybe",
		"I think so",
	):
		assert is_affirmative(t) is False, t


def test_is_negative_no_family():
	for t in (
		"no",
		"nope",
		"nah",
		"n",
		"not now",
		"not yet",
		"later",
		"cancel",
		"abort",
		"stop",
		"don't",
		"do not",
		"never",
		"no thanks",
		"no thank you",
	):
		assert is_negative(t) is True, t


def test_is_negative_multiword_and_leading_negative():
	for t in (
		"no thanks",
		"don't create it",
		"not now please",
		"do not create it",
		"never mind",
		"not really",
	):
		assert is_negative(t) is True, t


def test_is_not_negative_affirmative_or_neutral():
	for t in (
		"yes",
		"yeah",
		"sure",
		"go ahead",
		"do it",
		"correct",
		"maybe",
		"maybe later",
		"ok",
		"okay",
		"",
		"sure thing",
	):
		assert is_negative(t) is False, t


def test_affirmative_and_negative_are_disjoint():
	overlap = _AFFIRMATIVE & NEGATIVE
	assert not overlap, "affirmative and negative overlap: %s" % overlap


def test_empty_prompt_not_affirmative():
	assert is_affirmative("") is False
	assert is_negative("") is False


def test_whitespace_only_not_affirmative():
	assert is_affirmative("   ") is False
	assert is_negative("   ") is False


def test_auto_confirm_reply_classifies():
	# Affirmatives -> "confirm"
	for t in ("yes", "yeah", "sure", "go ahead", "create it", "do it"):
		assert auto_confirm_reply(t) == "confirm", t
	# Negatives -> "negative"
	for t in ("no", "nope", "not now", "cancel", "don't create it"):
		assert auto_confirm_reply(t) == "negative", t
	# Neutral -> "collect"
	for t in ("maybe", "steel rod", "ABC Traders", "", "   "):
		assert auto_confirm_reply(t) == "collect", t
