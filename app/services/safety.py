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
    RedFlag("loss of consciousness or seizure", ("passed out", "unconscious", "not waking up", "having a seizure", "seizure now")),
    RedFlag("severe bleeding", ("bleeding heavily", "won't stop bleeding", "will not stop bleeding", "vomiting blood", "coughing up blood")),
    RedFlag("severe allergic reaction", ("throat is closing", "throat closing", "swollen tongue", "anaphylaxis")),
    RedFlag("immediate self-harm risk", ("kill myself", "end my life", "suicidal", "hurt myself")),
)


def find_red_flags(text: str) -> list[str]:
    normalized = " ".join(text.lower().split())
    return [
        rule.label
        for rule in RED_FLAG_RULES
        if any(phrase in normalized for phrase in rule.phrases)
    ]
