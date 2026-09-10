"""
feedback_rules.py

One rule: if a pause lasts longer than the threshold for its linguistic
context, show the prompt for that context.

Thresholds and prompt wording are all in this file. Edit them here.
"""

# ── Thresholds, in seconds ────────────────────────────────────────────
# How long the writer must be stopped before a prompt appears, per context.
# Set a context to None to never prompt there.

THRESHOLDS = {
    "pre_theme":     2.0,   # clause not begun yet
    "theme_rheme":   1.5,   # Subject written, Process not yet written
    "within_rheme":  1.5,   # clause in progress
    "phrase":        1.5,   # at a phrase boundary
    "sentence":      1.5,   # clause looks complete
    "mid_word":      None,  # never prompt mid-word
}


# ── Prompts ───────────────────────────────────────────────────────────

PROMPTS = {
    "orientation": "What is this going to be about?",
    "process":     "What does this do, or what is it like?",
    "effect":      "What does this affect, and what follows from it?",
    "grounds":     "On what grounds?",
    "consequence": "What follows from this?",
    "viewpoint":   "Whose view is this, and does it hold?",
    "earlier":     "Why does this matter for the point you made earlier?",
    "connection":  "How does what comes next follow from this?",
}


def get_context(boundary_type, tier1):
    """Collapse the app's labels into one context name."""
    if boundary_type == "mid_word":
        return "mid_word"
    if boundary_type == "sentence_boundary":
        return "sentence"
    if boundary_type == "phrase_boundary":
        return "phrase"
    if tier1 == "pre_theme":
        return "pre_theme"
    if tier1 == "theme_rheme_boundary":
        return "theme_rheme"
    return "within_rheme"


def get_threshold_ms(context):
    """Threshold in milliseconds, or None if this context never prompts."""
    seconds = THRESHOLDS.get(context)
    return None if seconds is None else int(seconds * 1000)


def get_prompt(context, tier2=None, process=None):
    """The prompt for this context, or None."""
    tier2 = (tier2 or "").lower()
    process = (process or "").lower()

    if context == "mid_word":
        return None

    if context == "pre_theme":
        return PROMPTS["orientation"]

    if context == "theme_rheme":
        return PROMPTS["process"]

    if context == "sentence":
        return PROMPTS["connection"]

    # phrase and within_rheme: choose by what was just written
    if "attribute" in tier2 or process == "relational":
        return PROMPTS["grounds"]
    if process == "existential":
        return PROMPTS["consequence"]
    if process == "mental" or "phenomenon" in tier2:
        return PROMPTS["viewpoint"]
    if "goal" in tier2 or "recipient" in tier2:
        return PROMPTS["earlier"]
    if "process" in tier2:
        return PROMPTS["effect"]
    return PROMPTS["process"]


if __name__ == "__main__":
    cases = [
        ("word_boundary", "pre_theme", None, None),
        ("word_boundary", "theme_rheme_boundary", "Participant (Actor)", None),
        ("phrase_boundary", None, "Participant (Attribute)", "Relational"),
        ("phrase_boundary", None, "Participant (Goal/Phenomenon)", "Material"),
        ("sentence_boundary", None, None, None),
        ("mid_word", None, None, None),
    ]
    for b, t1, t2, pr in cases:
        c = get_context(b, t1)
        ms = get_threshold_ms(c)
        p = get_prompt(c, t2, pr)
        print("%-18s -> %-12s  %s  %s" % (
            b, c, ("%5d ms" % ms) if ms else "  never", p or "-"))