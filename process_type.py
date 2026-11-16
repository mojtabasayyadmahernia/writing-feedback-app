"""
TRANSITIVITY process types.

Classifies the Process of a clause into the five types used in the coding
scheme: Material, Mental, Relational, Verbal, Existential.

Departures from Fontaine (2012), following the project's coding decisions:

  * Behavioural processes are not a separate type. Where they are assigned
    is configurable, because the choice is contested and must match whatever
    the rest of a dataset was coded with -- see BEHAVIOURAL_AS below.
  * Identifying and Attributive are combined under Relational.

Verb-list based. A lexicon cannot see context, so a verb that crosses types
('see' as perception vs 'see' as understanding, 'have a shower' vs 'have a
car') is assigned its most frequent reading. Expect roughly the accuracy of
a first-pass automatic coding, not of a human annotator.
"""

import re
from typing import Optional

MATERIAL = "Material"
MENTAL = "Mental"
RELATIONAL = "Relational"
VERBAL = "Verbal"
EXISTENTIAL = "Existential"
BEHAVIOURAL = "Behavioural"

PROCESS_TYPES = (MATERIAL, MENTAL, RELATIONAL, VERBAL, EXISTENTIAL)

# Where behavioural processes ('laugh', 'cry', 'stare') are assigned.
#
# MENTAL follows the current specification.
# MATERIAL matches the manuscript's published coding scheme.
# BEHAVIOURAL keeps them as a sixth category, as the system network does.
#
# Sessions coded under different settings are not comparable.
BEHAVIOURAL_AS = MENTAL

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
    "think", "know", "believe", "understand", "realise", "realize",
    "remember", "forget", "imagine", "consider", "doubt", "suppose",
    "wonder", "recognise", "recognize", "expect", "assume", "reckon",
    "conclude", "decide", "learn", "reflect", "ponder",
    "see", "hear", "feel", "notice", "perceive", "watch", "sense", "smell",
    "like", "love", "hate", "want", "wish", "hope", "need", "prefer",
    "enjoy", "fear", "regret", "mind", "dislike", "appreciate", "value",
    "desire", "crave", "miss", "trust", "worry", "care",
}

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

COPULAR_WHEN_ATTRIBUTIVE = {
    "look", "feel", "sound", "taste", "smell", "appear", "seem", "grow",
    "turn", "prove", "come", "go", "get", "keep",
}

ATTRIBUTE_DEPS = {"acomp", "attr", "oprd"}


def _process_token(doc):
    root = None
    for token in doc:
        if token.dep_ == "ROOT":
            root = token
            break
    if root is None:
        return None
    if root.pos_ in ("VERB", "AUX"):
        return root
    for child in root.children:
        if child.dep_ in ("cop", "aux") and child.pos_ in ("VERB", "AUX"):
            return child
    for token in doc:
        if token.pos_ in ("VERB", "AUX"):
            return token
    return None


def _is_existential(doc, verb) -> bool:
    """
    True for existential clauses: expletive 'there' + be.

    An earlier version also treated 'it is / it was' as existential, per the
    project's coding note. Validation against 6,817 hand-annotated pauses
    removed that branch: of 337 pauses where expletive 'there' fired, 77%
    were hand-coded existential, but of 218 where the 'it' subject fired,
    only 3% were -- 55% were coded relational. Standard SFL agrees: 'It is a
    good idea' is relational with 'it' as Carrier.
    """
    if verb.lemma_ != "be":
        return False
    return any(token.dep_ == "expl" and token.lemma_ == "there" for token in doc)


def _has_attribute(verb) -> bool:
    return any(child.dep_ in ATTRIBUTE_DEPS for child in verb.children)


def _lemma_candidates(token):
    candidates = [token.lemma_.lower()]
    surface = token.text.lower()
    candidates.append(surface)
    if surface.endswith("ed"):
        candidates.append(surface[:-1])
        candidates.append(surface[:-2])
    if surface.endswith("ing"):
        candidates.append(surface[:-3] + "e")
        candidates.append(surface[:-3])
    if surface.endswith("s") and not surface.endswith("ss"):
        candidates.append(surface[:-1])
    return candidates


def _in_lexicon(token, lexicon) -> bool:
    return any(candidate in lexicon for candidate in _lemma_candidates(token))


def get_process_type(doc) -> Optional[str]:
    verb = _process_token(doc)
    if verb is None:
        return None
    lemma = verb.lemma_.lower()
    if _is_existential(doc, verb):
        return EXISTENTIAL
    if _in_lexicon(verb, VERBAL_VERBS):
        return VERBAL
    if lemma in COPULAR_WHEN_ATTRIBUTIVE and _has_attribute(verb):
        return RELATIONAL
    if lemma == "have":
        return RELATIONAL
    if _in_lexicon(verb, BEHAVIOURAL_VERBS):
        return BEHAVIOURAL_AS
    if _in_lexicon(verb, MENTAL_VERBS):
        return MENTAL
    if _in_lexicon(verb, RELATIONAL_VERBS):
        return RELATIONAL
    return MATERIAL


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
    if len(word) == 1:
        return True
    return word in ABBREVIATIONS


def current_clause(text: str) -> str:
    """
    The clause in progress -- or, when the writer has just closed one, the
    clause they just closed.

    Returning only the text after the last '.!?' leaves nothing to parse when
    a pause falls immediately after a full stop. That is the commonest single
    context in the validation corpus (1,996 of 6,817 pauses), and it was the
    largest source of missing output: 1,302 of the 1,959 pauses where no
    process could be assigned were this one case.

    Falling back to the completed clause raised coverage from 68% to 89% of
    pauses with no loss of agreement, and it is the more useful reading for
    live feedback -- 'you have just finished a clause' says something, an
    empty parse does not.

    The closing '.!?' is stripped so the last token of the returned clause is
    the last WORD. Left in place it would be punctuation, which resolves to
    no participant role.
    """
    bounds = [m.end() for m in _SENTENCE_END.finditer(text)
              if not _is_abbreviation(text, m.start())]
    if not bounds:
        return text

    trailing = text[bounds[-1]:]
    if trailing.strip():
        return trailing

    start = bounds[-2] if len(bounds) >= 2 else 0
    return text[start:bounds[-1]].rstrip(".!? \t\n")


def clause_process_type(nlp, text: str) -> Optional[str]:
    clause = current_clause(text).strip()
    if not clause:
        return None
    return get_process_type(nlp(clause))