"""
TRANSITIVITY process types.

Classifies the Process of a clause into the five types used in the coding
scheme: Material, Mental, Relational, Verbal, Existential.

Departures from Fontaine (2012), following the project's coding decisions:

  * Behavioural processes are not a separate type. Where they are assigned
    is configurable, because the choice is contested and must match whatever
    the rest of a dataset was coded with — see BEHAVIOURAL_AS below.
  * Identifying and Attributive are combined under Relational.

"""

import re
from typing import Optional

# ── Process types ────────────────────────────────────────────────────────
MATERIAL = "Material"
MENTAL = "Mental"
RELATIONAL = "Relational"
VERBAL = "Verbal"
EXISTENTIAL = "Existential"

PROCESS_TYPES = (MATERIAL, MENTAL, RELATIONAL, VERBAL, EXISTENTIAL)

# Where behavioural processes ('laugh', 'cry', 'stare') are assigned.
#
# Set to MENTAL to follow the current specification.
# Set to MATERIAL to match the manuscript's published coding scheme, which
# treats them as material on the grounds that the Behaver resembles an Actor
# and cannot project a clause.
#
# Sessions coded under different settings are not comparable, so this is
# recorded in the API's /health response.
BEHAVIOURAL_AS = MENTAL

# ── Verb lexicons, keyed on lemma ────────────────────────────────────────
VERBAL_VERBS = {
    "say", "tell", "ask", "reply", "answer", "state", "claim", "argue",
    "suggest", "mention", "report", "announce", "declare", "explain",
    "remark", "add", "insist", "admit", "deny", "promise", "warn", "urge",
    "shout", "whisper", "complain", "respond", "note", "observe", "point",
    "recount", "describe", "quote", "propose", "recommend", "advise",
    "protest", "confess", "reveal", "disclose", "assert", "maintain",
    "contend", "acknowledge", "concede", "emphasise", "emphasize", "stress",
}

MENTAL_VERBS = {
    # cognition
    "think", "know", "believe", "understand", "realise", "realize",
    "remember", "forget", "imagine", "consider", "doubt", "suppose",
    "wonder", "recognise", "recognize", "expect", "assume", "reckon",
    "conclude", "decide", "learn", "reflect", "ponder",
    # perception
    "see", "hear", "feel", "notice", "perceive", "watch", "sense", "smell",
    # affection and desire
    "like", "love", "hate", "want", "wish", "hope", "need", "prefer",
    "enjoy", "fear", "regret", "mind", "dislike", "appreciate", "value",
    "desire", "crave", "miss", "trust", "worry", "care",
}

# Behavioural: outward physiological or expressive behaviour. Assigned to
# BEHAVIOURAL_AS rather than being a type of its own.
BEHAVIOURAL_VERBS = {
    "laugh", "cry", "smile", "sigh", "breathe", "cough", "sneeze", "yawn",
    "frown", "stare", "gaze", "listen", "sleep", "dream", "weep", "chuckle",
    "grin", "blush", "shiver", "tremble", "gasp", "groan", "sob", "snore",
    "blink", "wink", "nod", "shrug", "grimace", "whimper", "giggle",
}

RELATIONAL_VERBS = {
    "be", "become", "seem", "appear", "remain", "stay", "constitute",
    "represent", "comprise", "consist", "belong", "own", "possess",
    "resemble", "equal", "mean", "signify", "include", "contain", "involve",
    "concern", "lack", "cost", "weigh", "measure", "total", "number",
    "amount", "count",
}

# Copular when they take an Attribute ('the soup tastes good'), and
# perception or behaviour otherwise ('he tasted the soup').
COPULAR_WHEN_ATTRIBUTIVE = {
    "look", "feel", "sound", "taste", "smell", "appear", "seem", "grow",
    "turn", "prove", "come", "go", "get", "keep",
}

ATTRIBUTE_DEPS = {"acomp", "attr", "oprd"}

# ── Detection ────────────────────────────────────────────────────────────
def _process_token(doc):
    """
    The token carrying the Process, or None if the clause has no verb yet.

    Prefers the lexical verb over its auxiliaries, so 'has been eating'
    resolves to 'eat' rather than 'have'.
    """
    root = None
    for token in doc:
        if token.dep_ == "ROOT":
            root = token
            break
    if root is None:
        return None

    if root.pos_ in ("VERB", "AUX"):
        return root

    # ROOT is nominal: a copula may still be attached ('the idea is good'
    # parses with 'good' as ROOT in some analyses).
    for child in root.children:
        if child.dep_ in ("cop", "aux") and child.pos_ in ("VERB", "AUX"):
            return child

    # Fall back to any finite verb in the clause.
    for token in doc:
        if token.pos_ in ("VERB", "AUX"):
            return token
    return None


def _is_existential(doc, verb) -> bool:
    """
    True for existential clauses.

    Two patterns are accepted:
      'there' + be   — the standard SFL existential
      'it' + be      — included per the project's coding scheme, though
                       most SFL treatments analyse this as Relational with
                       'it' as Carrier or Token. See the module note.
    """
    if verb.lemma_ != "be":
        return False
    for token in doc:
        if token.dep_ == "expl" and token.lemma_ == "there":
            return True
        if token.dep_ in ("nsubj", "nsubjpass") and token.lemma_ == "it":
            return True
    return False


def _has_attribute(verb) -> bool:
    """True if the verb takes an Attribute, making a copular reading right."""
    return any(child.dep_ in ATTRIBUTE_DEPS for child in verb.children)


def _has_object(verb) -> bool:
    return any(child.dep_ in ("dobj", "dative", "iobj") for child in verb.children)


def _lemma_candidates(token):
    """
    Lemmas to try, in order.

    spaCy's small model mislemmatises some regular past forms ('stared'
    becomes 'star'), which silently drops the verb out of every lexicon and
    defaults it to Material. Regular-inflection guesses are tried after the
    lemma so a mislemmatised verb still lands in the right set.
    """
    candidates = [token.lemma_.lower()]
    surface = token.text.lower()
    candidates.append(surface)
    if surface.endswith("ed"):
        candidates.append(surface[:-1])   # stared -> stare
        candidates.append(surface[:-2])   # walked -> walk
    if surface.endswith("ing"):
        candidates.append(surface[:-3] + "e")  # staring -> stare
        candidates.append(surface[:-3])        # walking -> walk
    if surface.endswith("s") and not surface.endswith("ss"):
        candidates.append(surface[:-1])   # stares -> stare
    return candidates


def _in_lexicon(token, lexicon) -> bool:
    return any(candidate in lexicon for candidate in _lemma_candidates(token))


def get_process_type(doc) -> Optional[str]:
    """
    Return the TRANSITIVITY process type of the clause, or None if no
    Process has been written yet.

    `doc` is a parsed spaCy Doc for the current clause.
    """
    verb = _process_token(doc)
    if verb is None:
        return None

    lemma = verb.lemma_.lower()

    # Existential is checked first: 'there is' would otherwise be Relational.
    if _is_existential(doc, verb):
        return EXISTENTIAL

    if _in_lexicon(verb, VERBAL_VERBS):
        return VERBAL

    # Copular-or-not verbs resolve on whether an Attribute is present.
    if lemma in COPULAR_WHEN_ATTRIBUTIVE and _has_attribute(verb):
        return RELATIONAL

    if lemma == "have":
        # Possessive 'have' is Relational; 'have a shower' is Material, but
        # the two are not distinguishable without a lexicon of light-verb
        # objects, so the more frequent possessive reading is taken.
        return RELATIONAL

    if _in_lexicon(verb, BEHAVIOURAL_VERBS):
        return BEHAVIOURAL_AS

    if _in_lexicon(verb, MENTAL_VERBS):
        return MENTAL

    if _in_lexicon(verb, RELATIONAL_VERBS):
        return RELATIONAL

    return MATERIAL


# ── Clause clipping and entry point ──────────────────────────────────────
# The Process belongs to the clause being written, not to the whole essay.
# Passing the full text would make spaCy's first ROOT come from an earlier
# sentence, so the text is cut back to the clause in progress first.

ABBREVIATIONS = {
    "dr", "mr", "mrs", "ms", "prof", "st", "jr", "sr",
    "e.g", "i.e", "etc", "vs", "cf", "fig", "no", "al",
}

_SENTENCE_END = re.compile(r"[.!?]")


def _is_abbreviation(text: str, index: int) -> bool:
    if text[index] != ".":
        return False
    preceding = re.search(r"([A-Za-z.]+)$", text[:index])
    if not preceding:
        return False
    word = preceding.group(1).lower()
    if len(word) == 1:        # an initial: 'J. R. R. Tolkien'
        return True
    return word in ABBREVIATIONS


def current_clause(text: str) -> str:
    """
    Return the text after the last sentence-final punctuation mark.

    'The cat sat. There is a' -> ' There is a'
    'Dr. Smith arrived'       -> 'Dr. Smith arrived'
    """
    for match in reversed(list(_SENTENCE_END.finditer(text))):
        if not _is_abbreviation(text, match.start()):
            return text[match.end():]
    return text


def clause_process_type(nlp, text: str) -> Optional[str]:
    """
    Process type of the clause in progress, or None if no Process has been
    written yet.

    `nlp` is a loaded spaCy model; `text` is everything up to the cursor.
    """
    clause = current_clause(text).strip()
    if not clause:
        return None
    return get_process_type(nlp(clause))