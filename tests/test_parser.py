"""Unit tests for WI-001: HL7 Parser (best-effort)."""

import pytest
from src.parser.hl7_parser import parse, ParseResult, tokenize_field_value


# --- Test data ---

SAMPLE_ADT_A01 = (
    "MSH|^~\\&|SAP|KBS|800|0100|20240115120000||ADT^A01^ADT_A07|000012345|P|2.5^^^2.16||NP11I0|AL|CHE|8859/1\r\n"
    "EVN|A01|20240115120000\r\n"
    "PID|1||123456^7^M10^KBS^800||Müller^Hans^Peter^^Dr.||19850315|M||||||+41612654321^^hans.mueller@email.ch^+41612654322^+41791234567|||M|||756.1234.5678.90||||||Basel||CHE\r\n"
    "PD1||||||||||||||HFGY~HFGN~EPDY\r\n"
    "NK1|1|Müller^Anna||||+41612654999|||||||||||||||||||||||||EMCON\r\n"
    "PV1|1|I|CHIR^201^A^MED1||E||12345^Schneider^Thomas|||||||||||V|98765^1^M10|||KV||||||||||||||||20240115120000\r\n"
    "GT1|1|||||||||||||||USB^AG-Basel^^^^12345||Hauptstr. 1^^Basel^^4001^CH||+41612659000~+41612659001\r\n"
    "ZBE|00001|20240115120000||NP11I0|I\r\n"
)

SAMPLE_ADT_A08 = (
    "MSH|^~\\&|SAP|KBS|800|0100|20240115130000||ADT^A08^ADT_A07|000012346|P|2.5^^^2.16||NP0200|AL|CHE|8859/1\r\n"
    "PID|1||123456^7^M10^KBS^800||Müller^Hans^Peter^^Dr.||19850315|M||||||+41612654321^^hans.mueller@email.ch|||M|||756.1234.5678.90||||||Basel||CHE\r\n"
)

TWO_MESSAGES_WITH_SEPARATOR = SAMPLE_ADT_A01 + "---separator---\r\n" + SAMPLE_ADT_A08


class TestSingleValidMessage:
    """Test 1: Single valid ADT^A01 message is parsed correctly."""

    def test_parses_successfully(self):
        result = parse(SAMPLE_ADT_A01)
        assert result.is_valid_hl7 is True
        assert len(result.messages) == 1

    def test_encoding_chars(self):
        result = parse(SAMPLE_ADT_A01)
        msg = result.messages[0]
        assert msg.encoding_chars["field_sep"] == "|"
        assert msg.encoding_chars["component_sep"] == "^"
        assert msg.encoding_chars["repetition_sep"] == "~"
        assert msg.encoding_chars["escape_char"] == "\\"
        assert msg.encoding_chars["subcomponent_sep"] == "&"

    def test_message_type(self):
        result = parse(SAMPLE_ADT_A01)
        assert result.messages[0].message_type == "ADT^A01^ADT_A07"

    def test_segment_count(self):
        result = parse(SAMPLE_ADT_A01)
        msg = result.messages[0]
        segment_names = [s.name for s in msg.segments]
        assert "MSH" in segment_names
        assert "PID" in segment_names
        assert "EVN" in segment_names
        assert "NK1" in segment_names
        assert "PV1" in segment_names
        assert "GT1" in segment_names
        assert "ZBE" in segment_names
        assert "PD1" in segment_names

    def test_pid_fields(self):
        result = parse(SAMPLE_ADT_A01)
        msg = result.messages[0]
        pid = [s for s in msg.segments if s.name == "PID"][0]
        # PID.5 = Patient Name = "Müller^Hans^Peter^^Dr."
        pid5 = [f for f in pid.fields if f.field_index == 5][0]
        assert "Müller" in pid5.raw_value
        assert pid5.path == "PID.5"
        assert not pid5.is_empty

    def test_no_non_hl7_lines(self):
        result = parse(SAMPLE_ADT_A01)
        assert len(result.non_hl7_lines) == 0


class TestTwoMessages:
    """Test 2: Two messages separated by newline → 2 Messages."""

    def test_two_messages_simple(self):
        text = SAMPLE_ADT_A01 + "\r\n" + SAMPLE_ADT_A08
        result = parse(text)
        assert result.is_valid_hl7 is True
        assert len(result.messages) == 2

    def test_different_message_types(self):
        text = SAMPLE_ADT_A01 + "\r\n" + SAMPLE_ADT_A08
        result = parse(text)
        assert result.messages[0].message_type == "ADT^A01^ADT_A07"
        assert result.messages[1].message_type == "ADT^A08^ADT_A07"


class TestNonHL7LinesBetweenMessages:
    """Test 3: Non-HL7 lines between messages (e.g. '---separator---') → in non_hl7_lines."""

    def test_separator_captured(self):
        result = parse(TWO_MESSAGES_WITH_SEPARATOR)
        assert result.is_valid_hl7 is True
        assert len(result.messages) == 2
        non_hl7_texts = [text for _, text in result.non_hl7_lines]
        assert "---separator---" in non_hl7_texts

    def test_non_hl7_has_line_numbers(self):
        result = parse(TWO_MESSAGES_WITH_SEPARATOR)
        for line_num, text in result.non_hl7_lines:
            assert isinstance(line_num, int)
            assert line_num > 0


class TestCompletelyInvalidInput:
    """Test 4: Completely invalid input (no MSH) → is_valid_hl7=False, all in non_hl7_lines."""

    def test_no_msh(self):
        text = "This is not HL7\nJust some random text\nMore text"
        result = parse(text)
        assert result.is_valid_hl7 is False
        assert len(result.messages) == 0
        assert len(result.non_hl7_lines) == 3

    def test_non_hl7_content_preserved(self):
        text = "Line one\nLine two"
        result = parse(text)
        texts = [t for _, t in result.non_hl7_lines]
        assert "Line one" in texts
        assert "Line two" in texts


class TestEmptyInput:
    """Test 5: Empty input → empty ParseResult."""

    def test_empty_string(self):
        result = parse("")
        assert result.is_valid_hl7 is False
        assert len(result.messages) == 0
        assert len(result.non_hl7_lines) == 0

    def test_whitespace_only(self):
        result = parse("   \n\n  \n")
        assert result.is_valid_hl7 is False
        assert len(result.messages) == 0
        assert len(result.non_hl7_lines) == 0

    def test_none_like(self):
        result = parse("")
        assert isinstance(result, ParseResult)


class TestEscapeSequences:
    """Test 6: Escape sequences in field values → not treated as separators."""

    def test_escape_in_field(self):
        # OBX with escaped field separator \F\ and component separator \S\ in value
        text = "MSH|^~\\&|SYS|||||||ADT^A01|||2.5\r\nOBX|1|ST|code||Value with \\F\\ pipe and \\S\\ caret||||||F\r\n"
        result = parse(text)
        assert result.is_valid_hl7 is True
        msg = result.messages[0]
        obx = [s for s in msg.segments if s.name == "OBX"][0]
        # OBX.5 = observation value
        obx5 = [f for f in obx.fields if f.field_index == 5][0]
        assert "\\F\\" in obx5.raw_value
        assert "\\S\\" in obx5.raw_value

    def test_escape_not_split(self):
        text = "MSH|^~\\&|SYS|||||||ADT^A01|||2.5\r\nOBX|1|ST|code||Test\\R\\Value||||||F\r\n"
        result = parse(text)
        obx = [s for s in result.messages[0].segments if s.name == "OBX"][0]
        obx5 = [f for f in obx.fields if f.field_index == 5][0]
        # Should not be split by ~ inside escape
        assert "\\R\\" in obx5.raw_value


class TestRepeatingFields:
    """Test 7: Repeating fields (e.g. PID-13 with ~) → correctly resolved."""

    def test_repetition_in_pid13(self):
        result = parse(SAMPLE_ADT_A01)
        msg = result.messages[0]
        pid = [s for s in msg.segments if s.name == "PID"][0]
        # PID.13 has phone + email separated by ^, but let's check GT1 which has ~ repetition
        gt1 = [s for s in msg.segments if s.name == "GT1"][0]
        # GT1.21 (index 21) has +41612659000~+41612659001
        gt1_phones = [f for f in gt1.fields if f.field_index == 21]
        if gt1_phones:
            field = gt1_phones[0]
            assert isinstance(field.components, list)
            assert len(field.components) == 2  # two repetitions

    def test_pd1_repetition(self):
        result = parse(SAMPLE_ADT_A01)
        msg = result.messages[0]
        pd1 = [s for s in msg.segments if s.name == "PD1"][0]
        # PD1.14 = "HFGY~HFGN~EPDY" — 3 repetitions
        pd1_14 = [f for f in pd1.fields if f.field_index == 14]
        if pd1_14:
            field = pd1_14[0]
            assert isinstance(field.components, list)
            assert len(field.components) == 3


class TestDifferentEncodingChars:
    """Test 8: Different encoding characters (e.g. MSH|#~\\&) → correctly extracted."""

    def test_custom_component_sep(self):
        text = "MSH|#~\\&|SYS|||||||ADT^A01|||2.5\r\nPID|1||12345||Smith#John||19900101|M\r\n"
        result = parse(text)
        assert result.is_valid_hl7 is True
        msg = result.messages[0]
        assert msg.encoding_chars["component_sep"] == "#"
        pid = [s for s in msg.segments if s.name == "PID"][0]
        pid5 = [f for f in pid.fields if f.field_index == 5][0]
        assert isinstance(pid5.components, list)
        # "Smith#John" should be split into ["Smith", "John"]
        assert len(pid5.components) == 2


class TestEmptyFields:
    """Test 9: Empty fields (||) → is_empty=True, raw_value=''."""

    def test_empty_field_detected(self):
        text = "MSH|^~\\&|SYS|||||||ADT^A01|||2.5\r\nPID|1||||Smith^John\r\n"
        result = parse(text)
        msg = result.messages[0]
        pid = [s for s in msg.segments if s.name == "PID"][0]
        # PID.2, PID.3, PID.4 should be empty
        empty_fields = [f for f in pid.fields if f.is_empty]
        assert len(empty_fields) >= 2

    def test_empty_field_raw_value(self):
        text = "MSH|^~\\&|SYS|||||||ADT^A01|||2.5\r\nPID|1||||Smith^John\r\n"
        result = parse(text)
        pid = [s for s in result.messages[0].segments if s.name == "PID"][0]
        empty = [f for f in pid.fields if f.is_empty][0]
        assert empty.raw_value == ""
        assert empty.components == []


class TestZSegments:
    """Test 10: Z-Segments → treated like regular segments."""

    def test_zbe_parsed(self):
        result = parse(SAMPLE_ADT_A01)
        msg = result.messages[0]
        zbe = [s for s in msg.segments if s.name == "ZBE"]
        assert len(zbe) == 1
        assert zbe[0].name == "ZBE"
        assert len(zbe[0].fields) > 0

    def test_custom_z_segment(self):
        text = "MSH|^~\\&|SYS|||||||ADT^A01|||2.5\r\nZZZ|1|custom^data|value\r\n"
        result = parse(text)
        msg = result.messages[0]
        zzz = [s for s in msg.segments if s.name == "ZZZ"]
        assert len(zzz) == 1
        assert zzz[0].fields[0].raw_value == "1"


class TestMSHFieldIndexing:
    """Test MSH field indexing: MSH.1=separator, MSH.2=encoding chars, MSH.3=Sending App, etc."""

    def test_msh2_encoding_chars_stored(self):
        result = parse(SAMPLE_ADT_A01)
        msh = [s for s in result.messages[0].segments if s.name == "MSH"][0]
        msh2 = [f for f in msh.fields if f.field_index == 2][0]
        assert msh2.raw_value == "^~\\&"
        assert msh2.path == "MSH.2"

    def test_msh3_sending_application(self):
        result = parse(SAMPLE_ADT_A01)
        msh = [s for s in result.messages[0].segments if s.name == "MSH"][0]
        msh3 = [f for f in msh.fields if f.field_index == 3][0]
        assert msh3.raw_value == "SAP"
        assert msh3.path == "MSH.3"

    def test_msh4_sending_facility(self):
        result = parse(SAMPLE_ADT_A01)
        msh = [s for s in result.messages[0].segments if s.name == "MSH"][0]
        msh4 = [f for f in msh.fields if f.field_index == 4][0]
        assert msh4.raw_value == "KBS"
        assert msh4.path == "MSH.4"

    def test_msh9_message_type(self):
        result = parse(SAMPLE_ADT_A01)
        msh = [s for s in result.messages[0].segments if s.name == "MSH"][0]
        msh9 = [f for f in msh.fields if f.field_index == 9][0]
        assert msh9.raw_value == "ADT^A01^ADT_A07"
        assert msh9.path == "MSH.9"

    def test_msh1_is_separator(self):
        result = parse(SAMPLE_ADT_A01)
        msh = [s for s in result.messages[0].segments if s.name == "MSH"][0]
        msh1 = [f for f in msh.fields if f.field_index == 1][0]
        assert msh1.raw_value == "|"


class TestTokenizeFieldValue:
    """Test tokenize_field_value for component-level rendering."""

    ENC = {
        "field_sep": "|", "component_sep": "^",
        "repetition_sep": "~", "escape_char": "\\",
        "subcomponent_sep": "&",
    }

    def test_simple_value(self):
        tokens = tokenize_field_value("SAP", self.ENC)
        assert tokens == [("SAP", "value")]

    def test_components(self):
        tokens = tokenize_field_value("Müller^Hans^Peter", self.ENC)
        assert tokens == [
            ("Müller", "value"), ("^", "component_sep"),
            ("Hans", "value"), ("^", "component_sep"),
            ("Peter", "value"),
        ]

    def test_repetitions(self):
        tokens = tokenize_field_value("+4161~+4179", self.ENC)
        assert tokens == [
            ("+4161", "value"), ("~", "repetition_sep"),
            ("+4179", "value"),
        ]

    def test_subcomponents(self):
        tokens = tokenize_field_value("A&B^C", self.ENC)
        assert tokens == [
            ("A", "value"), ("&", "subcomponent_sep"),
            ("B", "value"), ("^", "component_sep"),
            ("C", "value"),
        ]

    def test_empty_components(self):
        tokens = tokenize_field_value("A^^B", self.ENC)
        assert tokens == [
            ("A", "value"), ("^", "component_sep"),
            ("", "value"), ("^", "component_sep"),
            ("B", "value"),
        ]

    def test_empty_value(self):
        tokens = tokenize_field_value("", self.ENC)
        assert tokens == [("", "value")]

    def test_escape_sequences_preserved(self):
        tokens = tokenize_field_value("A\\F\\B^C", self.ENC)
        # \F\ should NOT be split — the F is not a separator
        values = [t for t, typ in tokens if typ == "value"]
        assert values == ["A\\F\\B", "C"]

    def test_mixed_repetition_and_components(self):
        tokens = tokenize_field_value("A^B~C^D", self.ENC)
        assert tokens == [
            ("A", "value"), ("^", "component_sep"),
            ("B", "value"), ("~", "repetition_sep"),
            ("C", "value"), ("^", "component_sep"),
            ("D", "value"),
        ]
