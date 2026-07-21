import re
from dataclasses import dataclass


URGENT_CARE_MESSAGE = (
    "Your message may describe a medical emergency. Please call emergency services "
    "now or go to the nearest emergency department. If you are in the U.S. or Canada, "
    "call 911. Do not wait for this chat. If possible, have someone stay with you."
)


@dataclass(frozen=True)
class RedFlag:
    label: str
    phrases: tuple[str, ...]


RED_FLAG_RULES = (
    RedFlag("possible heart or breathing emergency", ("chest pain", "chest pressure", "can't breathe", "cannot breathe", "trouble breathing", "severe shortness of breath")),
    RedFlag("possible stroke symptoms", ("face drooping", "facial droop", "slurred speech", "sudden weakness", "one-sided weakness", "one sided weakness")),
    RedFlag("sudden worst-ever headache", ("worst headache of my life", "worst-ever headache", "worst ever headache", "thunderclap headache")),
    RedFlag("loss of consciousness or seizure", ("passed out", "unconscious", "not waking up", "having a seizure", "seizure now")),
    RedFlag("severe bleeding", ("bleeding heavily", "won't stop bleeding", "will not stop bleeding", "vomiting blood", "vomited blood", "coughing up blood", "black tarry stools", "black, tarry stools", "tarry stools")),
    RedFlag("severe allergic reaction", ("throat is closing", "throat closing", "swollen tongue", "anaphylaxis")),
    RedFlag("immediate self-harm risk", ("kill myself", "end my life", "suicidal", "hurt myself","ending my life","want to die", "want to kill myself", "want to end my life", "want to hurt myself")),
)


NEGATION_BEFORE_PHRASE = re.compile(
    r"(?:\bno\b|\bnot\b|\bwithout\b|\bnever\b|\bden(?:y|ies|ied)\b|"
    r"\bdon't have\b|\bdo not have\b)[^.!?;]{0,50}$"
)


def _is_reported(normalized: str, phrase: str) -> bool:
    start = normalized.find(phrase)
    while start != -1:
        preceding_text = normalized[max(0, start - 70) : start]
        if NEGATION_BEFORE_PHRASE.search(preceding_text) is None:
            return True
        start = normalized.find(phrase, start + len(phrase))
    return False


def find_red_flags(text: str) -> list[str]:
    normalized = " ".join(text.lower().split())
    return [
        rule.label
        for rule in RED_FLAG_RULES
        if any(_is_reported(normalized, phrase) for phrase in rule.phrases)
    ]
