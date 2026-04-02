"""WI-005: Tests for anonymization engine.

DoD: No original value of a selected field in output.
     Roundtrip: output is valid HL7 (re-parseable).
"""

import pytest

from src.engine.anonymizer import anonymize
from src.parser.hl7_parser import parse


SINGLE_MSG = (
    "MSH|^~\\&|SYS1|FAC1|SYS2|FAC2|20240101120000||ADT^A01|MSG001|P|2.5\r\n"
    "PID|1||12345||Müller^Hans^Peter||19850315|M|||Hauptstr. 1^^Zürich^^8001\r\n"
    "NK1|1|Meier^Anna|SPO||044-1234567\r\n"
    "PV1|1|I|||||||Doc^Smith^John"
)

TWO_MSGS = (
    "MSH|^~\\&|SYS1|FAC1|SYS2|FAC2|20240101||ADT^A01|MSG001|P|2.5\r\n"
    "PID|1||12345||Müller^Hans||19850315|M\r\n"
    "\r\n"
    "MSH|^~\\&|SYS1|FAC1|SYS2|FAC2|20240101||ADT^A01|MSG002|P|2.5\r\n"
    "PID|1||67890||Meier^Lisa||19900720|F"
)


class TestBasicAnonymization:
    """Simple field selected → value replaced with mask."""

    def test_simple_field_masked(self):
        r = parse(SINGLE_MSG)
        # Select PID.3 (patient ID "12345") in message 0
        result = anonymize(r, {(0, "PID.3")})
        pid_line = [l for l in result.split("\n") if l.startswith("PID")][0]
        assert "***" in pid_line
        assert "12345" not in pid_line

    def test_unselected_field_preserved(self):
        r = parse(SINGLE_MSG)
        result = anonymize(r, {(0, "PID.3")})
        # PID.8 (Sex "M") should remain
        assert "|M|" in result

    def test_custom_mask(self):
        r = parse(SINGLE_MSG)
        result = anonymize(r, {(0, "PID.3")}, mask="XXX")
        pid_line = [l for l in result.split("\n") if l.startswith("PID")][0]
        assert "XXX" in pid_line
        assert "12345" not in pid_line
        assert "***" not in pid_line


class TestStructurePreservation:
    """Separators ^~\\& must remain. Empty fields stay empty."""

    def test_component_separators_preserved(self):
        r = parse(SINGLE_MSG)
        # Select individual component PID.5.1 (Müller) but not PID.5.2 (Hans)
        result = anonymize(r, {(0, "PID.5.1")})
        assert "Müller" not in result
        assert "Hans" in result
        # ^ separator between components must still be there
        assert "***^Hans^Peter" in result

    def test_all_components_selected(self):
        r = parse(SINGLE_MSG)
        # Select all 3 components of PID.5
        result = anonymize(r, {(0, "PID.5.1"), (0, "PID.5.2"), (0, "PID.5.3")})
        assert "***^***^***" in result
        assert "Müller" not in result
        assert "Hans" not in result
        assert "Peter" not in result

    def test_empty_fields_stay_empty(self):
        r = parse(SINGLE_MSG)
        # PID.2 is empty (||) — selecting it should not insert mask
        # (it has no ValueWidget, so it can't be selected, but engine shouldn't break)
        result = anonymize(r, set())
        # Verify the empty field between PID.1 and PID.3 remains
        lines = result.split("\n")
        pid_line = [l for l in lines if l.startswith("PID")][0]
        assert "|1||12345|" in pid_line

    def test_pipe_separators_count_preserved(self):
        r = parse(SINGLE_MSG)
        original_pid = [l for l in SINGLE_MSG.split("\n") if l.startswith("PID")][0].rstrip("\r")
        original_pipes = original_pid.count("|")

        result = anonymize(r, {(0, "PID.5.1"), (0, "PID.3")})
        result_pid = [l for l in result.split("\n") if l.startswith("PID")][0]
        result_pipes = result_pid.count("|")
        assert result_pipes == original_pipes

    def test_msh_encoding_chars_preserved(self):
        r = parse(SINGLE_MSG)
        result = anonymize(r, {(0, "PID.5.1")})
        lines = result.split("\n")
        msh_line = lines[0]
        assert msh_line.startswith("MSH|^~\\&|")


class TestNoOriginalValueLeaks:
    """DoD: no original value of any selected field appears in the output."""

    def test_all_pid_name_components_gone(self):
        r = parse(SINGLE_MSG)
        selections = {(0, "PID.5.1"), (0, "PID.5.2"), (0, "PID.5.3")}
        result = anonymize(r, selections)
        for name in ("Müller", "Hans", "Peter"):
            assert name not in result, f"Original value '{name}' leaked into output"

    def test_address_components_gone(self):
        r = parse(SINGLE_MSG)
        selections = {(0, "PID.11.1"), (0, "PID.11.3"), (0, "PID.11.5")}
        result = anonymize(r, selections)
        for val in ("Hauptstr. 1", "Zürich", "8001"):
            assert val not in result, f"Original value '{val}' leaked into output"

    def test_nk1_phone_gone(self):
        r = parse(SINGLE_MSG)
        result = anonymize(r, {(0, "NK1.5")})
        assert "044-1234567" not in result

    def test_multiple_fields_masked(self):
        r = parse(SINGLE_MSG)
        selections = {
            (0, "PID.3"),
            (0, "PID.5.1"), (0, "PID.5.2"), (0, "PID.5.3"),
            (0, "PID.7"),
            (0, "NK1.5"),
        }
        result = anonymize(r, selections)
        for val in ("12345", "Müller", "Hans", "Peter", "19850315", "044-1234567"):
            assert val not in result, f"'{val}' leaked"


class TestRoundtrip:
    """DoD: Output is valid HL7 — re-parseable by our parser."""

    def test_roundtrip_single_message(self):
        r = parse(SINGLE_MSG)
        selections = {(0, "PID.5.1"), (0, "PID.3"), (0, "NK1.2.1")}
        output = anonymize(r, selections)

        r2 = parse(output)
        assert r2.is_valid_hl7
        assert len(r2.messages) == 1
        assert len(r2.messages[0].segments) == len(r.messages[0].segments)

    def test_roundtrip_two_messages(self):
        r = parse(TWO_MSGS)
        assert len(r.messages) == 2
        selections = {(0, "PID.5.1"), (1, "PID.5.1")}
        output = anonymize(r, selections)

        r2 = parse(output)
        assert r2.is_valid_hl7
        assert len(r2.messages) == 2

    def test_roundtrip_segment_count_stable(self):
        r = parse(SINGLE_MSG)
        output = anonymize(r, {(0, "PID.5.1")})
        r2 = parse(output)
        for orig_msg, anon_msg in zip(r.messages, r2.messages):
            assert len(anon_msg.segments) == len(orig_msg.segments)

    def test_roundtrip_message_type_preserved(self):
        r = parse(SINGLE_MSG)
        output = anonymize(r, {(0, "PID.5.1")})
        r2 = parse(output)
        assert r2.messages[0].message_type == r.messages[0].message_type


class TestMultiMessage:
    """Selections scoped to specific messages by msg_index."""

    def test_only_selected_message_masked(self):
        r = parse(TWO_MSGS)
        # Only mask PID.5 in message 0
        result = anonymize(r, {(0, "PID.5.1")})
        assert "Müller" not in result
        assert "Meier" in result  # message 1 untouched

    def test_both_messages_masked(self):
        r = parse(TWO_MSGS)
        result = anonymize(r, {(0, "PID.5.1"), (1, "PID.5.1")})
        assert "Müller" not in result
        assert "Meier" not in result


class TestEdgeCases:
    """Empty input, no selections, non-HL7 input."""

    def test_no_selections_returns_original(self):
        r = parse(SINGLE_MSG)
        result = anonymize(r, set())
        assert "Müller" in result
        assert "12345" in result

    def test_empty_input(self):
        r = parse("")
        result = anonymize(r, set())
        assert result == ""

    def test_non_hl7_input_passthrough(self):
        r = parse("This is not HL7\nJust plain text")
        result = anonymize(r, set())
        assert "This is not HL7" in result
        assert "Just plain text" in result

    def test_empty_mask(self):
        r = parse(SINGLE_MSG)
        result = anonymize(r, {(0, "PID.3")}, mask="")
        pid_line = [l for l in result.split("\n") if l.startswith("PID")][0]
        assert "12345" not in pid_line
        # Field should be empty now but structure preserved
        r2 = parse(result)
        assert r2.is_valid_hl7


class TestLengthPreserve:
    """WI-023: Length-preserving mask strategy."""

    def test_length_matches_original(self):
        r = parse(SINGLE_MSG)
        result = anonymize(r, {(0, "PID.5.1")}, mask="*", length_preserve=True)
        pid_line = [l for l in result.split("\n") if l.startswith("PID")][0]
        # "Müller" is 6 chars → should be "******"
        assert "******" in pid_line
        assert "Müller" not in pid_line

    def test_length_preserve_components(self):
        r = parse(SINGLE_MSG)
        result = anonymize(
            r, {(0, "PID.5.1"), (0, "PID.5.2")},
            mask="#", length_preserve=True,
        )
        pid_line = [l for l in result.split("\n") if l.startswith("PID")][0]
        assert "Müller" not in pid_line
        assert "Hans" not in pid_line
        # "Hans" = 4 chars → "####"
        assert "####" in pid_line


class TestConsistentPseudonymization:
    """WI-024: Same value → same pseudonym across messages."""

    def test_same_value_same_pseudonym(self):
        # Build two messages with the same patient name
        msg = (
            "MSH|^~\\&|A|B|C|D|20240101||ADT^A01|1|P|2.5\r\n"
            "PID|1||1||Smith^John||19900101|M\r\n"
            "\r\n"
            "MSH|^~\\&|A|B|C|D|20240101||ADT^A01|2|P|2.5\r\n"
            "PID|1||2||Smith^John||19900101|M"
        )
        r = parse(msg)
        result = anonymize(
            r,
            {(0, "PID.5.1"), (0, "PID.5.2"), (1, "PID.5.1"), (1, "PID.5.2")},
            consistent=True,
        )
        lines = [l for l in result.split("\n") if l.startswith("PID")]
        # Both PID lines should have the same pseudonym for "Smith"
        # Smith → ANON-1 in both messages
        assert "ANON-1" in lines[0]
        assert "ANON-1" in lines[1]
        assert "Smith" not in result

    def test_different_values_different_pseudonyms(self):
        r = parse(SINGLE_MSG)
        result = anonymize(
            r, {(0, "PID.5.1"), (0, "PID.5.2")}, consistent=True,
        )
        pid_line = [l for l in result.split("\n") if l.startswith("PID")][0]
        assert "ANON-1" in pid_line
        assert "ANON-2" in pid_line
        assert "Müller" not in pid_line
        assert "Hans" not in pid_line
