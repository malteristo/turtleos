"""The house speaker says the talk, and the page is not in what it is given.

The reader is `answer_body`: a voice pipeline asks for a sentence and receives
only the words that may be spoken. A planted phrase that lives only above the
talk must be absent from that body.
"""

from __future__ import annotations

import json
import unittest

import house_speaker as speaker

PAGE = "PAGE-SECRET the longer writing stays written"
TALK = "The afternoon is still open."


def _reply_with_a_page() -> str:
    return f"{PAGE}\n\nThe talk\n{TALK}"


class SpokenTests(unittest.TestCase):
    def test_a_reply_without_a_talk_is_spoken_whole(self) -> None:
        self.assertEqual(speaker.spoken("It is three."), "It is three.")

    def test_the_page_is_not_spoken_when_a_talk_is_marked(self) -> None:
        heard = speaker.spoken(_reply_with_a_page())
        self.assertEqual(heard, TALK)
        self.assertNotIn("PAGE-SECRET", heard or "")

    def test_a_bold_mark_is_the_same_mark(self) -> None:
        self.assertEqual(speaker.spoken(f"page\n\n**The talk**\n{TALK}"), TALK)

    def test_the_last_mark_is_the_one_that_is_spoken(self) -> None:
        text = f"The talk\nnot this\n\nThe talk\n{TALK}"
        self.assertEqual(speaker.spoken(text), TALK)

    def test_an_empty_talk_does_not_fall_back_to_the_page(self) -> None:
        self.assertIsNone(speaker.spoken(f"{PAGE}\n\nThe talk\n"))

    def test_a_mention_of_the_words_inside_a_sentence_is_not_a_mark(self) -> None:
        text = "I wrote The talk in the margin, and the afternoon is open."
        self.assertEqual(speaker.spoken(text), text)

    def test_empty_is_silence(self) -> None:
        self.assertIsNone(speaker.spoken("  "))
        self.assertIsNone(speaker.spoken(None))

    def test_an_aside_is_not_spoken(self) -> None:
        heard = speaker.spoken("Hello.\n\n-# PAGE-SECRET")
        self.assertEqual(heard, "Hello.")
        self.assertNotIn("PAGE-SECRET", heard or "")


class AnswerBodyTests(unittest.TestCase):
    def test_the_pipeline_receives_the_talk_and_not_the_page(self) -> None:
        body = {
            "model": "home",
            "messages": [
                {"role": "user", "content": "an earlier sentence"},
                {"role": "assistant", "content": "an earlier reply"},
                {"role": "user", "content": "What should I do with the afternoon?"},
            ],
        }
        seen: list[str] = []

        def turn(sentence: str) -> str:
            seen.append(sentence)
            return _reply_with_a_page()

        response = speaker.answer_body(body, turn)
        content = response["message"]["content"]
        self.assertEqual(seen, ["What should I do with the afternoon?"])
        self.assertEqual(content, TALK)
        self.assertNotIn("PAGE-SECRET", json.dumps(response))
        self.assertTrue(response["done"])

    def test_an_empty_talk_tells_him_the_reply_is_written(self) -> None:
        body = {"messages": [{"role": "user", "content": "hello"}]}

        def turn(_sentence: str) -> str:
            return f"{PAGE}\n\nThe talk\n"

        content = speaker.answer_body(body, turn)["message"]["content"]
        self.assertEqual(content, speaker.WRITTEN_IN_HOME)
        self.assertNotIn("PAGE-SECRET", content)

    def test_no_sentence_is_not_a_turn(self) -> None:
        seen: list[str] = []

        def turn(sentence: str) -> str:
            seen.append(sentence)
            return "should not run"

        content = speaker.answer_body({"messages": []}, turn)["message"]["content"]
        self.assertEqual(content, speaker.DID_NOT_HEAR)
        self.assertEqual(seen, [])

    def test_a_failed_turn_does_not_speak_the_exception(self) -> None:
        def turn(_sentence: str) -> str:
            raise RuntimeError("PAGE-SECRET boom")

        content = speaker.answer_body(
            {"messages": [{"role": "user", "content": "hello"}]}, turn
        )["message"]["content"]
        self.assertEqual(content, speaker.DID_NOT_ANSWER)
        self.assertNotIn("PAGE-SECRET", content)

    def test_a_list_of_text_parts_is_still_one_sentence(self) -> None:
        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "What time is it?"}],
                }
            ]
        }
        self.assertEqual(speaker.sentence_of(body), "What time is it?")


if __name__ == "__main__":
    unittest.main()
