"""
Resolving participant roles from process type.

Tier 2 in the writing app reads a spaCy dependency label and maps it to an
SFL function. On its own, a dependency label cannot say which participant
role it realises: an `nsubj` is an Actor in a material clause, a Senser in
a mental one, a Sayer in a verbal one. The app therefore emitted an
unresolved disjunction, 'Participant (Actor/Senser/Carrier)'.

Process type supplies the missing half. This module combines the two.

    nsubj + Material    -> Actor
    nsubj + Mental      -> Senser
    nsubj + Verbal      -> Sayer
    dobj  + Material    -> Goal
    dobj  + Mental      -> Phenomenon

Source of the mapping
---------------------
FIRST_PARTICIPANT is taken directly from the realization statements in
networks/transitivity.json of the system-network-builder project, which
encodes Halliday & Matthiessen (2014), IFG4 ch. 5:

    material     ["+Process", "+Actor"]
    mental       ["+Process", "+Senser"]
    behavioural  ["+Process", "+Behaver"]
    verbal       ["+Process", "+Sayer"]
    existential  ["+Process", "+Existent"]
    relational   ["+Process"]            <- no participant at this delicacy
    RELATIONAL_MODE / attributive  ["+Carrier", "+Attribute"]
    RELATIONAL_MODE / identifying  ["+Token", "+Value"]

SECOND_PARTICIPANT is NOT in that file. The network stops at the delicacy
where only the first participant is declared, so Goal, Phenomenon, Verbiage
and Behaviour are added here by hand from IFG4 ch. 5 and are marked as such.

The table is vendored rather than imported. system-network-builder is a
grammar engine that deliberately does not import spaCy, and the writing app
should not take a runtime dependency on it. `verify_against_network()` below
re-derives the table from the JSON when a copy is available, so the two can
be checked against each other without being coupled.

Standard library only.
"""

from typing import Optional

# ── First participant: straight from the network's realization statements ──
FIRST_PARTICIPANT = {
    "Material":    "Actor",
    "Mental":      "Senser",
    "Behavioural": "Behaver",
    "Verbal":      "Sayer",
    "Existential": "Existent",
    # The app collapses attributive and identifying into one Relational
    # category, so the attributive participant is used. An identifying
    # clause would properly be Token, not Carrier.
    "Relational":  "Carrier",
}

# ── Second participant: hand-added from IFG4 ch. 5, not in the network ────
SECOND_PARTICIPANT = {
    "Material":    "Goal",
    "Mental":      "Phenomenon",
    "Behavioural": "Behaviour",
    "Verbal":      "Verbiage",
    "Relational":  "Attribute",
    # An existential clause has one participant only; the Existent surfaces
    # as the complement of 'there is', so it is handled in resolve_role().
    "Existential": "Existent",
}

# Indirect object / dative: only some process types have a third role.
RECIPIENT = {
    "Material": "Recipient",
    "Verbal":   "Receiver",
}

# Dependency labels that realise the first participant.
FIRST_DEPS = {"nsubj"}

# Passive subjects realise the second participant, not the first:
# 'the mountain was climbed' has Goal as Subject.
PASSIVE_SUBJECT_DEPS = {"nsubjpass"}

# Dependency labels that realise the second participant.
SECOND_DEPS = {"dobj", "attr", "acomp", "oprd"}

# Dependency labels that realise a Recipient or Receiver.
RECIPIENT_DEPS = {"iobj", "dative"}


def resolve_role(dep: str, process: Optional[str], *, is_existential_complement: bool = False) -> Optional[str]:
    """
    Return the SFL participant role for a dependency label given the clause's
    process type, or None if the pair does not resolve to a participant.

    `dep`     : spaCy dependency label of the token.
    `process` : process type from process_type.py, or None if no Process has
                been written yet.
    """
    if not process:
        return None

    # 'There is a problem' — the Existent is the complement, not the subject.
    if process == "Existential":
        if dep in SECOND_DEPS or is_existential_complement:
            return "Existent"
        if dep in FIRST_DEPS:
            return None  # the 'there' is a placeholder, not a participant
        return None

    if dep in FIRST_DEPS:
        return FIRST_PARTICIPANT.get(process)
    if dep in PASSIVE_SUBJECT_DEPS:
        return SECOND_PARTICIPANT.get(process)
    if dep in SECOND_DEPS:
        return SECOND_PARTICIPANT.get(process)
    if dep in RECIPIENT_DEPS:
        return RECIPIENT.get(process)
    return None


def describe_role(dep: str, process: Optional[str]) -> Optional[str]:
    """
    A display string for the resolved role, or None when it cannot resolve.

    'Participant (Actor)' rather than the bare role name, to stay consistent
    with the existing Tier 2 label format.
    """
    role = resolve_role(dep, process)
    if role is None:
        return None
    return f"Participant ({role})"


# ── Consistency check against the network definition ─────────────────────
def verify_against_network(path="networks/transitivity.json"):
    """
    Re-derive FIRST_PARTICIPANT from a copy of the system-network-builder
    network file and report any disagreement.

    Returns a list of mismatch strings; empty means the table agrees with the
    network. Raises FileNotFoundError if the network file is not present,
    which is expected — the table is vendored precisely so the app runs
    without it.
    """
    import json

    with open(path, encoding="utf-8") as handle:
        network = json.load(handle)

    derived = {}
    for system in network["systems"]:
        if system["id"] == "PROCESS_TYPE":
            for term in system["terms"]:
                for item in term.get("realization", []):
                    if item != "+Process" and item.startswith("+"):
                        derived[term["id"].capitalize()] = item[1:]
        if system["id"] == "RELATIONAL_MODE":
            for term in system["terms"]:
                if term["id"] == "attributive":
                    derived["Relational"] = term["realization"][0][1:]

    mismatches = []
    for process, role in derived.items():
        if FIRST_PARTICIPANT.get(process) != role:
            mismatches.append(
                f"{process}: table says {FIRST_PARTICIPANT.get(process)!r}, "
                f"network says {role!r}"
            )
    for process in FIRST_PARTICIPANT:
        if process not in derived:
            mismatches.append(f"{process}: in table but not derivable from network")
    return mismatches


# ── Clause-level entry point, mirroring clause_process_type() ────────────
def clause_participant_role(nlp, text: str, process: Optional[str]) -> Optional[str]:
    """
    Participant role of the last element of the clause in progress, or None.

    Computed independently of boundary type. This matters: in the writing
    app, `analyze_linguistic_context()` returns early at a phrase boundary,
    so a clause ending in an object never reaches the Tier 2 branch at all.
    Every object case -- 'She climbed the mountain', 'I saw the change' --
    is a phrase boundary. Resolving the role only inside Tier 2 would
    therefore never fire on exactly the clauses where the Goal/Phenomenon
    distinction is at stake.

    `nlp`     : loaded spaCy model.
    `text`    : everything up to the cursor.
    `process` : process type from clause_process_type(), or None.
    """
    from process_type import current_clause

    clause = current_clause(text).strip()
    if not clause or not process:
        return None
    doc = nlp(clause)
    if len(doc) == 0:
        return None
    return resolve_role(doc[-1].dep_, process)