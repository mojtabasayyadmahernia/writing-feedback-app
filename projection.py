"""
Which Process the pause belongs to: projection, clause complexes and verb
chains.

The app used to take the process type of the sentence's main verb (the
spaCy ROOT) and to resolve every participant role against it. Two things
went wrong with that, compared with the hand coding.

1. Process type (sentence level).  The hand coding gives a sentence the
   type of the clause being written, with three refinements:

     * Projection.  A clause projected by a mental or verbal process takes
       the projecting process: in 'I think he broke the window' the type is
       Mental, from 'think'.
     * Clause complexes.  A coordinated clause ('..., yet some people still
       prefer to') has its own process. A dependent clause ('... because it
       saves time') takes the process of the clause it depends on.
     * Verb chains.  In 'want to get to know' or 'allows you to focus on',
       the Process is the LAST verb of the chain ('know'), the earlier ones
       are phase, conation or modulation.

2. Participant role.  A participant's role is assigned by the verb it
   depends on, not by the sentence's main verb. In 'I think he broke the
   window', 'the window' is Goal of 'broke' (Material), not Phenomenon of
   'think'. So the role is resolved against the process of the verb the
   last word depends on, while the process type shown for the sentence
   stays Mental.

Evaluation (v0.12), against the hand-annotated corpus, rules chosen on one
half of the writers and checked on the other:

                         chosen-on half      held-out half
    process type kappa   0.539 -> 0.557      0.472 -> 0.496
    Mental recall        43% -> 53%          41% -> 51%
    role kappa           0.436 -> 0.759      0.328 -> 0.610
    Goal recall          63% -> 91%          61% -> 84%
"""

from typing import Optional

import process_type as PT
from clause_boundary import _last_word

# Clauses that rank in the clause complex. A coordinated clause counts too,
# but only if the clause it is coordinated with ranks (see clause_head).
RANKING_DEPS = {"ROOT", "advcl", "ccomp", "parataxis"}


def _is_verb(token) -> bool:
    return token.pos_ in ("VERB", "AUX")


def classify_verb(doc, verb) -> str:
    """Process type of a given verb (get_process_type() picks the ROOT)."""
    lemma = verb.lemma_.lower()
    if lemma == "be" and any(c.dep_ == "expl" and c.lemma_ == "there" for c in verb.children):
        return PT.EXISTENTIAL
    if PT._in_lexicon(verb, PT.VERBAL_VERBS):
        return PT.VERBAL
    if lemma in PT.COPULAR_WHEN_ATTRIBUTIVE and PT._has_attribute(verb):
        return PT.RELATIONAL
    if lemma == "have":
        return PT.RELATIONAL
    if PT._in_lexicon(verb, PT.BEHAVIOURAL_VERBS):
        return PT.BEHAVIOURAL_AS
    if PT._in_lexicon(verb, PT.MENTAL_VERBS):
        return PT.MENTAL
    if PT._in_lexicon(verb, PT.RELATIONAL_VERBS):
        return PT.RELATIONAL
    return PT.MATERIAL


def _first_conjunct(verb):
    guard = 0
    while verb.dep_ == "conj" and verb.head.i != verb.i and guard < 8:
        verb = verb.head
        guard += 1
    return verb


def clause_head(token):
    """
    The verb heading the ranking clause `token` belongs to, or None.

    Embedded clauses (relative clauses, clauses inside a group) are passed
    through. A coordinated verb starts a clause of its own only if the verb
    it is coordinated with heads a ranking clause: in 'ways to find and
    meet', 'meet' is coordinated with embedded 'find', so it is embedded too.
    """
    t = token
    for _ in range(40):
        if _is_verb(t):
            if t.dep_ in RANKING_DEPS:
                return t
            if t.dep_ == "conj":
                first = _first_conjunct(t)
                if _is_verb(first) and first.dep_ in RANKING_DEPS:
                    return t
        if t.head.i == t.i:
            return None
        t = t.head
    return None


def chain_end(verb):
    """The last verb of a chain like 'want to get to know' (xcomp)."""
    for _ in range(6):
        nxt = [c for c in verb.children if c.dep_ == "xcomp" and _is_verb(c)]
        if not nxt:
            break
        verb = nxt[-1]
    return verb


def projecting_verb(doc, verb):
    """The outermost mental or verbal verb projecting the clause of `verb`."""
    found = None
    h = verb
    while h.dep_ == "ccomp" and h.head.i != h.i and _is_verb(h.head):
        if classify_verb(doc, h.head) in (PT.MENTAL, PT.VERBAL):
            found = h.head
        h = h.head
    return found


def _parse(nlp, text):
    clause = PT.current_clause(text).strip()
    if not clause:
        return None, None, None
    doc = nlp(clause)
    root = PT._process_token(doc)
    if root is None:
        return doc, None, None
    return doc, root, _last_word(doc)


def sentence_process_type(nlp, text: str) -> Optional[str]:
    """
    Process type of the sentence being written, as the hand coding assigns
    it: the clause in progress, lifted to the clause it depends on, then to
    a projecting mental or verbal process; within a verb chain, the last
    verb.
    """
    doc, root, last = _parse(nlp, text)
    if root is None:
        return None
    head = clause_head(last) if last is not None else None
    head = head if head is not None else root
    for _ in range(6):
        if head.dep_ != "advcl" or head.head.i == head.i:
            break
        up = clause_head(head.head)
        if up is None:
            break
        head = up
    projector = projecting_verb(doc, head)
    if projector is not None:
        return classify_verb(doc, projector)
    return classify_verb(doc, chain_end(head))


def role_process_type(nlp, text: str) -> Optional[str]:
    """
    Process type of the verb the last word depends on: the process that
    assigns that word's participant role. 'I think he broke the window' ->
    Material (from 'broke'), so 'the window' is Goal.
    """
    doc, root, last = _parse(nlp, text)
    if root is None:
        return None
    g = last
    for _ in range(40):
        if g is None or _is_verb(g) or g.head.i == g.i:
            break
        g = g.head
    verb = g if g is not None and _is_verb(g) else root
    return classify_verb(doc, verb)