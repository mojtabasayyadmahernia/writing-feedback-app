"""
Nominal groups in progress.
How a group in progress is recognised
-------------------------------------
Working backwards from the last word, the run of words that can only
PRECEDE a Thing is collected: articles and possessive determiners (the, a,
my, their), a possessor with 's (the man's), adjectives, numerals and
intensifiers (very, quite). The group is unfinished when

  * the run ends in a determiner or 's ('I broke the'), or
  * the run contains a determiner and ends in a modifier ('the very
    beautiful', 'the two'), or
  * the run is a bare adjective after a verb or preposition ('I broke
    beautiful').

A bare adjective after a copular verb is NOT a group in progress: in 'The
window is very beautiful' the adjective is the Attribute itself.

These are judgements about a prefix. 'I broke the two' could be complete
('the two' = both of them); the app takes the more frequent reading, that
the Thing is still to come.

Which role the group will fill
------------------------------
The role depends on the slot the group occupies, read off the word before
it:

    after a verb                 -> object slot   -> Goal / Phenomenon / Verbiage
    after a copular verb         -> complement    -> Attribute / Existent
    after 'by' in a passive      -> agent         -> Actor
    after a preposition          -> inside a prepositional phrase -> Circumstance
                                    (unless the phrase post-modifies a noun,
                                    'one of the', in which case the group
                                    belongs to that noun's role)
    after 'and'/'or'             -> same slot as the first conjunct
    at the start of a clause     -> Subject slot  -> no role yet

The Subject case gets no role on purpose. A participant role is assigned by
the Process, and a Subject is written before its Process: until the verb is
there, 'the government' could still turn out to be Actor, Senser, Sayer or
Carrier. This matches the rest of the app (resolve_role() returns nothing
without a Process).
"""

from dataclasses import dataclass
from typing import Optional

from process_participant import resolve_role, FIRST_PARTICIPANT
from clause_boundary import current_sentence

PARTICIPANT = "Participant"
CIRCUMSTANCE = "Circumstance"

ARTICLES = {"the", "a", "an", "every", "each", "another"}

INTENSIFIERS = {
    "very", "quite", "rather", "extremely", "fairly", "highly", "really",
    "so", "too", "most", "more", "less", "least", "particularly",
    "especially", "incredibly", "truly",
}

COPULAR = {
    "be", "become", "seem", "remain", "appear", "look", "sound", "feel",
    "stay", "turn", "grow", "get", "prove",
}

NOMINAL = {"NOUN", "PROPN", "PRON", "NUM"}

# Dependency labels of a nominal group that fills a participant slot.
SLOT_DEPS = {"nsubj", "nsubjpass", "dobj", "attr", "oprd", "dative", "iobj"}


@dataclass
class GroupInProgress:
    slot: Optional[str]      # dependency the finished group will carry
    role: Optional[str]      # participant role, when it can be resolved
    element: str             # PARTICIPANT or CIRCUMSTANCE


def _is_determiner(token) -> bool:
    return token.lower_ in ARTICLES or token.tag_ in ("PRP$", "POS")


def _is_modifier(token) -> bool:
    if token.pos_ in ("ADJ", "NUM"):
        return True
    return token.pos_ == "ADV" and token.lower_ in INTENSIFIERS


def _open_run(tokens):
    """
    The run of pre-Thing words at the end of `tokens`, and the index of the
    token just before it (-1 if the run starts the clause).
    """
    i = len(tokens) - 1
    run = []
    while i >= 0:
        token = tokens[i]
        if token.tag_ == "POS":
            # A possessor: "the man's" -- take the 's and the noun group
            # it attaches to.
            run.insert(0, token)
            i -= 1
            while i >= 0 and (tokens[i].pos_ in ("NOUN", "PROPN")
                              or _is_determiner(tokens[i])
                              or _is_modifier(tokens[i])):
                run.insert(0, tokens[i])
                i -= 1
            continue
        if _is_determiner(token) or _is_modifier(token):
            run.insert(0, token)
            i -= 1
            continue
        break
    return run, i


def _is_unfinished(run, before) -> bool:
    if not run:
        return False
    last = run[-1]
    if _is_determiner(last):
        return True
    if any(_is_determiner(t) for t in run):
        return True
    # A bare adjective, with no determiner. Unfinished only where a nominal
    # group must follow: after a non-copular verb or a preposition.
    if last.pos_ == "ADJ" and before is not None:
        if before.pos_ == "ADP":
            return True
        if before.pos_ in ("VERB", "AUX") and before.lemma_.lower() not in COPULAR:
            return True
    return False


def _slot(tokens, before_index, process):
    """Which slot the unfinished group occupies. Returns (slot, element)."""
    j = before_index
    # Skip focusing adverbs: 'broke only the', 'is also a'.
    while j >= 0 and tokens[j].pos_ == "ADV" and tokens[j].lower_ not in INTENSIFIERS:
        j -= 1
    if j < 0:
        return "nsubj", PARTICIPANT
    before = tokens[j]

    if before.pos_ in ("CCONJ",):
        # 'the window and the' -- same slot as the first conjunct.
        k = j - 1
        if k >= 0 and tokens[k].pos_ in NOMINAL and tokens[k].dep_ in SLOT_DEPS:
            return tokens[k].dep_, PARTICIPANT
        if k >= 0 and tokens[k].pos_ in NOMINAL and tokens[k].dep_ == "pobj":
            return "pobj", CIRCUMSTANCE
        return "nsubj", PARTICIPANT     # a new clause is starting

    if before.pos_ in ("SCONJ", "PUNCT") or before.dep_ == "mark":
        return "nsubj", PARTICIPANT

    if before.pos_ == "ADP":
        if before.lower_ == "by" and before.dep_ == "agent":
            return "agent", PARTICIPANT
        head = before.head
        if head.pos_ in NOMINAL and head.dep_ in SLOT_DEPS:
            # 'one of the' -- the phrase post-modifies a participant.
            return head.dep_, PARTICIPANT
        return "pobj", CIRCUMSTANCE

    if before.pos_ in ("VERB", "AUX"):
        if (before.lemma_.lower() in COPULAR
                and process in ("Relational", "Existential")):
            return "attr", PARTICIPANT
        return "dobj", PARTICIPANT

    if before.pos_ in NOMINAL and before.dep_ in ("dative", "iobj", "dobj"):
        # 'I gave him the' -- second object.
        return "dobj", PARTICIPANT

    return None, PARTICIPANT


def nominal_group_in_progress(nlp, text: str, process: Optional[str]) -> Optional[GroupInProgress]:
    """
    If the text before the cursor ends inside an unfinished nominal group,
    return what that group is and which role it will fill. Otherwise None.

    `process` is the clause's process type from process_type.py.
    """
    sentence = current_sentence(text).strip()
    if not sentence:
        return None
    tokens = [t for t in nlp(sentence) if not t.is_space]
    if not tokens or tokens[-1].is_punct:
        return None

    run, before_index = _open_run(tokens)
    before = tokens[before_index] if before_index >= 0 else None
    if not _is_unfinished(run, before):
        return None

    slot, element = _slot(tokens, before_index, process)

    if slot is None or element == CIRCUMSTANCE or slot in ("nsubj", "nsubjpass"):
        # Subject: the Process that assigns its role is not written yet.
        role = None
    elif slot == "agent":
        role = FIRST_PARTICIPANT.get(process) if process else None
    else:
        role = resolve_role(slot, process)

    return GroupInProgress(slot=slot, role=role, element=element)