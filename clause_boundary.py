"""
Clause and sentence completeness from grammar, not punctuation.

The app used to recognise a boundary only from the mark the writer typed:
'.', '!' or '?' meant a sentence boundary, and nothing else could. A
sentence that is grammatically complete but not yet punctuated -- 'Online
dating gives people a wider choice of partners' with the cursor after
'partners' -- was reported as a phrase or word boundary, although the
hand coding calls it 'end sentence'.

This module decides from the parse whether the clause the writer is in has
been completed. It is used in two places in main.py:

  * text ending in ',', ';' or ':': a complete clause before the mark is a
    clause boundary ('Although it rained,'), anything else stays a phrase
    boundary ('In 2020,').
  * text with no mark at all: see unmarked_ending() below. A complete
    sentence is a sentence boundary even though no full stop has been typed
    ('...and behavioural preferences'), because that is how the hand coding
    treats it: 'end sentence' marks where the sentence COULD end, and
    writers often pause there and then carry on.

How unmarked endings are labelled (v0.11)
-----------------------------------------
  * a complete sentence with no mark  -> sentence boundary, whatever its
    length: 'The boy broke the window' is a sentence.
  * ... unless it ends on its verb     -> phrase boundary
    ('connections form': the verbal group has just ended, and the hand
    coding codes that as 'end VP'). Set VERB_FINAL_IS_GROUP = False to
    report these as sentence boundaries too.

Checked against the hand-annotated corpus with writers split in two halves
(rule chosen on one, checked on the other). On the held-out half, recall of
hand 'end sentence' rose from 59% to 82%, precision of the app's sentence
boundary was 61%, and kappa over the six location categories rose from
0.343 to 0.408. (v0.10 also treated sentences under 8 words as phrase
boundaries; that was dropped because a short complete sentence is still a
sentence.)

How completeness is judged
--------------------------
1. The last word must not be one that needs something after it: a
   determiner, a preposition with no object, a conjunction, an auxiliary,
   a possessive, a modifier, or a Subject (the verb comes after it).
2. Walking up the parse from the last word, the first ranking clause reached
   must be headed by a verb. Embedded clauses (relative clauses, clauses
   inside a nominal group) are passed through: ending a relative clause does
   not end the clause it is embedded in.
3. A finite clause needs a Subject, unless it is a coordinated clause
   sharing the first conjunct's Subject ('I came and saw'). Imperatives and
   non-finite clauses need none.
4. Verbs that cannot stand without a complement -- 'be', 'become', 'make',
   'need', 'want', projecting verbs like 'think' and 'say' -- must have one.
   'The problem is' and 'I think' are not complete clauses.

This is a heuristic over a parser that sees unfinished text, so expect
errors. Rule 4 in particular uses a short verb list rather than full
valency information.
"""

from process_type import _SENTENCE_END, _is_abbreviation

CLAUSE_BOUNDARY = "clause_boundary"

# Dependency labels of a clause that ranks in its own right (in SFL terms,
# a clause in a clause complex rather than one embedded in a group).
RANKING_DEPS = {"ROOT", "advcl", "conj", "ccomp", "parataxis"}

SUBJECT_DEPS = {"nsubj", "nsubjpass", "expl", "csubj", "csubjpass"}

# Anything that can fill a verb's complement slot.
COMPLEMENT_DEPS = {
    "dobj", "attr", "acomp", "ccomp", "xcomp", "oprd", "prep", "dative",
    "advmod", "npadvmod", "prt", "agent", "advcl", "pcomp",
}

# A last word with one of these relations is waiting for its head or its
# object to be written.
DANGLING_DEPS = {
    "det", "predet", "poss", "case", "amod", "nummod", "quantmod",
    "compound", "nmod", "cc", "preconj", "mark", "aux", "auxpass", "neg",
    "prep", "agent",
} | SUBJECT_DEPS

DANGLING_POS = {"CCONJ", "SCONJ"}
DANGLING_TAGS = {"TO", "PRP$", "POS", "WDT", "WP$"}

# The parser sometimes tags a clause-final article as a pronoun ('sat on
# the' -> 'the' = pobj), and an intensifier as a modifier of the verb ('is
# very' -> 'very' = advmod of 'is'). These words cannot end a clause.
DANGLING_WORDS = {
    "the", "a", "an", "every", "each", "its", "their", "our", "my", "your",
    "whose", "very", "quite", "rather", "extremely", "fairly", "highly",
}

FINITE_TAGS = {"VBD", "VBZ", "VBP", "MD"}

# Verbs that do not form a complete clause without a complement.
NEEDS_COMPLEMENT = {
    # relational
    "be", "become", "seem", "remain", "include", "contain", "mean",
    "represent", "involve", "require", "lack", "resemble",
    # material, obligatorily transitive
    "make", "put", "give", "provide", "cause", "allow", "let", "bring",
    "take", "use", "reach", "affect", "prevent", "create", "offer",
    "have", "get",
    # mental and verbal, projecting
    "need", "want", "think", "believe", "consider", "say", "tell",
    "argue", "claim", "suggest", "state", "mention", "assume", "realise",
    "realize", "show", "indicate",
}

_CLOSERS = " \t\n\"')]}”’"
_SOFT_MARKS = ",;:"


def current_sentence(text: str) -> str:
    """Text after the last sentence-final mark (abbreviations ignored)."""
    bounds = [m.end() for m in _SENTENCE_END.finditer(text)
              if not _is_abbreviation(text, m.start())]
    return text[bounds[-1]:] if bounds else text


def _last_word(doc):
    for token in reversed(doc):
        if not (token.is_punct or token.is_space):
            return token
    return None


def _is_verb(token) -> bool:
    return token.pos_ in ("VERB", "AUX")


def _ranking_head(token):
    """
    Walk up from `token` to the head of the ranking clause it belongs to.

    Returns (head, verbs_on_path). `head` is None when the walk reaches the
    root without finding a verb, i.e. the text so far is a fragment.
    """
    verbs = []
    current = token
    while True:
        if _is_verb(current):
            verbs.append(current)
            if current.dep_ in RANKING_DEPS:
                if current.dep_ != "conj" or _is_verb(current.head):
                    return current, verbs
        # spaCy builds a new Token object on every .head access, so the
        # root test compares positions, not identity.
        if current.head.i == current.i:
            return None, verbs
        current = current.head


def _is_finite(verb) -> bool:
    if verb.tag_ in FINITE_TAGS:
        return True
    return any(child.dep_ in ("aux", "auxpass") and child.tag_ in FINITE_TAGS
               for child in verb.children)


def _has_subject(verb) -> bool:
    return any(child.dep_ in SUBJECT_DEPS for child in verb.children)


def _lacks_complement(verb) -> bool:
    if verb.lemma_.lower() not in NEEDS_COMPLEMENT:
        return False
    if any(child.dep_ == "auxpass" for child in verb.children):
        return False   # passive: 'the cake was made' is complete
    return not any(child.dep_ in COMPLEMENT_DEPS for child in verb.children)


def doc_is_complete_clause(doc) -> bool:
    """True if the parsed text ends at the end of a complete clause."""
    last = _last_word(doc)
    if last is None:
        return False

    # Rule 1: the last word is waiting for something.
    if last.dep_ in DANGLING_DEPS:
        return False
    if last.pos_ in DANGLING_POS or last.tag_ in DANGLING_TAGS:
        return False
    if last.lower_ in DANGLING_WORDS:
        return False
    if last.pos_ == "ADP" and last.dep_ != "prt":
        return False

    # Rule 2: the clause must have a verb.
    head, verbs = _ranking_head(last)
    if head is None:
        return False

    # Rule 3: a finite clause needs a Subject, unless coordinated.
    if head.dep_ != "conj" and _is_finite(head) and not _has_subject(head):
        return False

    # Rule 4: verbs that need a complement must have one.
    if any(_lacks_complement(verb) for verb in verbs):
        return False

    return True


# A complete clause that ends on its verb ('connections form') is reported as
# the end of its verbal group, as the hand coding does ('end VP'). Set to
# False to report it as a sentence boundary instead.
VERB_FINAL_IS_GROUP = True

SENTENCE = "sentence"
GROUP = "group"


def unmarked_ending(nlp, text: str):
    """
    For text with no closing mark: what has just been completed.

    Returns SENTENCE if the sentence could end here, GROUP if the clause is
    complete but ends on its verb (see VERB_FINAL_IS_GROUP), and None if no
    clause is complete.
    """
    sentence = current_sentence(text).strip()
    if not sentence:
        return None
    doc = nlp(sentence)
    if not doc_is_complete_clause(doc):
        return None
    last = _last_word(doc)
    if VERB_FINAL_IS_GROUP and last.pos_ in ("VERB", "AUX"):
        return GROUP
    return SENTENCE


def ends_complete_clause(nlp, text: str) -> bool:
    """
    True if `text` (everything up to the cursor) ends where a clause is
    grammatically complete. Trailing ',', ';', ':' and closing quotes or
    brackets are ignored, so 'Although it rained,' counts.
    """
    sentence = current_sentence(text).rstrip(_CLOSERS)
    sentence = sentence.rstrip(_SOFT_MARKS).rstrip(_CLOSERS)
    if not sentence.strip():
        return False
    return doc_is_complete_clause(nlp(sentence.strip()))