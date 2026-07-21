import unittest

from app.models.chats import IntakeCoverage, IntakeTurnDecision
from app.services.chat_service import _build_follow_up_reply


def decision(transition: str) -> IntakeTurnDecision:
    return IntakeTurnDecision(
        coverage=IntakeCoverage(
            onset_and_duration=True,
            location=True,
            character_or_quality=True,
            severity_zero_to_ten=True,
            aggravating_or_relieving_factors=True,
            associated_symptoms=True,
            relevant_history_and_prior_episodes=True,
            medications_and_supplements=False,
            known_allergies=False,
        ),
        transition=transition,
        follow_up_question="What medications are you taking?",
    )


class FollowUpReplyTests(unittest.TestCase):
    def test_drops_transition_that_duplicates_question(self) -> None:
        reply = _build_follow_up_reply(
            decision("What medications are you taking?")
        )

        self.assertEqual(reply, "What medications are you taking?")
        self.assertEqual(reply.count("What medications are you taking"), 1)

    def test_preserves_acknowledgement_before_duplicated_question(self) -> None:
        reply = _build_follow_up_reply(
            decision("Thanks. What medications are you taking?")
        )

        self.assertEqual(reply, "Thanks. What medications are you taking?")
        self.assertEqual(reply.count("What medications are you taking"), 1)

    def test_preserves_normal_short_transition(self) -> None:
        reply = _build_follow_up_reply(decision("Noted."))

        self.assertEqual(reply, "Noted. What medications are you taking?")
        self.assertEqual(reply.count("?"), 1)


if __name__ == "__main__":
    unittest.main()
