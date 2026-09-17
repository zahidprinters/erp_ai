# ---------------------------------------------------------------------------
# Voice on/off toggle — persistent per-user voice preference.
#
# Single responsibility: manage voice enable/disable state.
# Stores preference in the User doc (via a custom field) or system settings.
# ---------------------------------------------------------------------------
import frappe


def is_voice_enabled(user=None):
    """Return True if voice output is enabled for the user.

        Checks (in order):
    1. Admin master toggle (AI Settings.speaker_enabled) — if off, voice is OFF for everyone
    2. User-level preference (custom field on User)
    3. System-level default (AI Settings.voice_enabled_by_default)
    4. Default: False (voice off for safety/privacy)
    """
    user = user or frappe.session.user

    # Admin master toggle — overrides everything
    try:
        master = frappe.db.get_single_value("AI Settings", "speaker_enabled")
        if not master:
            return False
    except Exception:
        pass

    # Check user preference
    try:
        pref = frappe.db.get_value("User", user, "ai_voice_enabled")
        if pref is not None:
            return bool(pref)
    except Exception:
        pass

    # Check system default
    try:
        default = frappe.db.get_single_value("AI Settings", "voice_enabled_by_default")
        if default is not None:
            return bool(default)
    except Exception:
        pass

    return False


def set_voice_enabled(enabled, user=None):
    """Set voice preference for a user. Returns True on success."""
    user = user or frappe.session.user
    try:
        frappe.db.set_value("User", user, "ai_voice_enabled", 1 if enabled else 0)
        frappe.db.commit()
        return True
    except Exception:
        # Field may not exist yet — that's OK, just skip
        return False


def toggle_voice(user=None):
    """Toggle voice on/off. Returns the new state."""
    user = user or frappe.session.user
    current = is_voice_enabled(user)
    new_state = not current
    set_voice_enabled(new_state, user)
    return new_state
