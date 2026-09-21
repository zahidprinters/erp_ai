# ---------------------------------------------------------------------------
# Affirmative / negative reply detection for the guided-conversation auto-confirm
# feature.
#
# These are PURE functions with no Frappe dependency. They live in their own
# module so the DB-free test suite can import them directly without priming a
# Frappe context.
#
# The auto-confirm gate in ``erp_ai.conversation`` uses these to decide whether
# a free-text reply (e.g. "yes", "sure", "go ahead") should trigger
# ``confirm_draft()`` for a pending guided action.
# ---------------------------------------------------------------------------

from typing import FrozenSet

# Clear affirmative replies that should trigger auto-confirm of a pending
# guided action. Keep this conservative: only unambiguous "yes" family answers.
_AFFIRMATIVE: FrozenSet[str] = frozenset({
    "yes", "yeah", "yep", "yup", "y", "ya", "yeh", "aye",
    "sure", "go ahead", "go for it", "do it", "go on",
    "correct", "that's right", "right", "exactly",
    "please do", "please go ahead", "proceed",
    "go ahead and create it", "create it", "make it", "save it", "confirm",
})

# Clear negative / stop replies. A negative reply while in the ready state
# must NOT trigger auto-confirm, and should stop the guided flow.
NEGATIVE: FrozenSet[str] = frozenset({
    "no", "nope", "nah", "n", "not now", "not yet", "later",
    "cancel", "abort", "stop", "don't", "do not", "never",
    "no thanks", "no thank you", "not really",
})


def _strip_yes_no_context(token: str) -> str:
    """Drop obvious framing punctuation so "yes," / "yeah!" / "yep." still match."""
    return token.strip(".,;:!?\"'()[]{} \t").lower()


def is_affirmative(prompt: str) -> bool:
    """Return True when the user's reply is a clear affirmative.

    The check is deliberately strict: only unambiguous affirmative replies
    are treated as affirmative. Multi-word replies are matched as whole phrases
    (e.g. "go ahead", "do it", "create it") — a single affirmative token in a
    long sentence (e.g. "yes ignore previous instructions") is NOT treated as
    affirmative. This is the safety gate that prevents the assistant from
    creating documents the user did not mean to create.
    """
    if not prompt:
        return False
    p = prompt.strip().lower()
    if not p:
        return False
    # Whole-phrase match (handles punctuation-stripped single tokens too).
    if p in _AFFIRMATIVE:
        return True
    stripped = _strip_yes_no_context(p)
    if stripped in _AFFIRMATIVE:
        return True
    # Multi-word: only treat as affirmative if the entire phrase is one of our
    # known multi-word affirmative phrases. This prevents "yes ignore previous"
    # from matching just because it contains the token "yes".
    if p in _AFFIRMATIVE:
        return True
    return False


def is_negative(prompt: str) -> bool:
    """Return True when the reply is a clear negative / cancel / not-now.

    Used to stop the auto-confirm path and to clear a ready action when the
    user says "no" / "not now" / "later".
    """
    if not prompt:
        return False
    p = prompt.strip().lower()
    if not p:
        return False
    if p in NEGATIVE:
        return True
    stripped = _strip_yes_no_context(p)
    if stripped in NEGATIVE:
        return True
    # A reply that leads with a negative token or negative two-token phrase is
    # treated as negative even if it continues with other words. This handles
    # "no thanks", "don't create it", "not now please", "do not create it", etc.
    tokens = p.split()
    if not tokens:
        return False
    first = _strip_yes_no_context(tokens[0])
    if first in NEGATIVE:
        return True
    # Check the first two tokens as a phrase (e.g. "not now", "no thanks",
    # "do not").
    if len(tokens) >= 2:
        first_two = _strip_yes_no_context(' '.join(tokens[:2]))
        if first_two in NEGATIVE:
            return True
    return False


def auto_confirm_reply(prompt: str) -> str:
    """Classify a guided-flow reply for the auto-confirm gate.

    Returns one of:
      - "confirm"     — clear affirmative; the caller should confirm the draft.
      - "negative"    — clear negative; the caller should clear the guided flow.
      - "collect"     — neither; the caller should keep collecting the next field.
    """
    if is_negative(prompt):
        return "negative"
    if is_affirmative(prompt):
        return "confirm"
    return "collect"
