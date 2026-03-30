"""WI-001: Best-effort HL7 v2.x Parser."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class HL7Field:
    raw_value: str
    components: list
    field_index: int
    segment_name: str
    path: str
    is_empty: bool


@dataclass
class HL7Segment:
    name: str
    fields: list[HL7Field]
    raw_text: str


@dataclass
class HL7Message:
    segments: list[HL7Segment]
    encoding_chars: dict
    message_type: str
    raw_text: str


@dataclass
class ParseResult:
    messages: list[HL7Message] = field(default_factory=list)
    non_hl7_lines: list[tuple[int, str]] = field(default_factory=list)
    is_valid_hl7: bool = False



def _protect_escapes(text: str, escape_char: str) -> str:
    """Replace HL7 escape sequences with placeholders so separators inside
    escape sequences are not misinterpreted."""
    result = text
    esc = escape_char
    for seq, placeholder in [
        (f"{esc}F{esc}", "\x00F\x00"),
        (f"{esc}S{esc}", "\x00S\x00"),
        (f"{esc}T{esc}", "\x00T\x00"),
        (f"{esc}R{esc}", "\x00R\x00"),
        (f"{esc}E{esc}", "\x00E\x00"),
    ]:
        result = result.replace(seq, placeholder)
    return result


def _restore_escapes(text: str, escape_char: str) -> str:
    """Restore placeholders back to real HL7 escape sequences."""
    esc = escape_char
    for placeholder, seq in [
        ("\x00F\x00", f"{esc}F{esc}"),
        ("\x00S\x00", f"{esc}S{esc}"),
        ("\x00T\x00", f"{esc}T{esc}"),
        ("\x00R\x00", f"{esc}R{esc}"),
        ("\x00E\x00", f"{esc}E{esc}"),
    ]:
        text = text.replace(placeholder, seq)
    return text


def _split_components(value: str, component_sep: str, subcomponent_sep: str) -> list:
    """Split a field value into components, each split into subcomponents."""
    if not value:
        return []
    components = value.split(component_sep)
    result = []
    for comp in components:
        subs = comp.split(subcomponent_sep)
        result.append(subs if len(subs) > 1 else comp)
    return result


def _split_repetitions(value: str, repetition_sep: str, component_sep: str,
                       subcomponent_sep: str) -> list:
    """Split a field value by repetition separator, then into components."""
    reps = value.split(repetition_sep)
    if len(reps) == 1:
        return _split_components(value, component_sep, subcomponent_sep)
    return [_split_components(r, component_sep, subcomponent_sep) for r in reps]


def _extract_encoding_chars(msh_line: str) -> dict:
    """Extract encoding characters from MSH segment.
    MSH.1 = field separator (character right after 'MSH')
    MSH.2 = encoding characters (next 4 chars): component, repetition, escape, subcomponent
    """
    field_sep = msh_line[3]  # character after "MSH"

    # MSH.2 are the characters between first and second field separator
    parts = msh_line.split(field_sep)
    enc_str = parts[1] if len(parts) > 1 else "^~\\&"

    return {
        "field_sep": field_sep,
        "component_sep": enc_str[0] if len(enc_str) > 0 else "^",
        "repetition_sep": enc_str[1] if len(enc_str) > 1 else "~",
        "escape_char": enc_str[2] if len(enc_str) > 2 else "\\",
        "subcomponent_sep": enc_str[3] if len(enc_str) > 3 else "&",
    }


def _parse_segment(line: str, encoding_chars: dict) -> HL7Segment:
    """Parse a single HL7 segment line into an HL7Segment."""
    fs = encoding_chars["field_sep"]
    cs = encoding_chars["component_sep"]
    rs = encoding_chars["repetition_sep"]
    esc = encoding_chars["escape_char"]
    ss = encoding_chars["subcomponent_sep"]

    segment_name = line[:3]
    is_msh = segment_name == "MSH"

    # Protect escape sequences before splitting
    protected = _protect_escapes(line, esc)
    raw_fields = protected.split(fs)

    fields: list[HL7Field] = []

    for i, raw in enumerate(raw_fields):
        # MSH is special: MSH.1 = field separator (implicit), MSH.2 = encoding chars (parts[1])
        # After split: parts[0]="MSH", parts[1]=enc_chars, parts[2]=MSH.3, parts[3]=MSH.4, ...
        if is_msh:
            if i == 0:
                # MSH segment name — not a real field, skip
                continue
            if i == 1:
                # MSH.1 is the field separator — store as-is
                fields.append(HL7Field(
                    raw_value=fs,
                    components=[fs],
                    field_index=1,
                    segment_name=segment_name,
                    path=f"{segment_name}.1",
                    is_empty=False,
                ))
                # MSH.2 is the encoding characters — store from parts[1]
                enc_restored = _restore_escapes(raw, esc)
                fields.append(HL7Field(
                    raw_value=enc_restored,
                    components=list(enc_restored),
                    field_index=2,
                    segment_name=segment_name,
                    path=f"{segment_name}.2",
                    is_empty=enc_restored == "",
                ))
                continue
            field_index = i + 1  # parts[2]=MSH.3, parts[3]=MSH.4, etc.
        else:
            if i == 0:
                # Segment name — not a real field, skip
                continue
            field_index = i

        restored = _restore_escapes(raw, esc)
        is_empty = restored == ""

        components = _split_repetitions(raw, rs, cs, ss) if not is_empty else []
        # Restore escape sequences in components
        components = _restore_components(components, esc)

        fields.append(HL7Field(
            raw_value=restored,
            components=components,
            field_index=field_index,
            segment_name=segment_name,
            path=f"{segment_name}.{field_index}",
            is_empty=is_empty,
        ))

    return HL7Segment(
        name=segment_name,
        fields=fields,
        raw_text=line,
    )


def _restore_components(components: list, esc: str) -> list:
    """Recursively restore escape sequences in a nested component structure."""
    result = []
    for item in components:
        if isinstance(item, list):
            result.append(_restore_components(item, esc))
        elif isinstance(item, str):
            result.append(_restore_escapes(item, esc))
        else:
            result.append(item)
    return result


def _parse_single_message(lines: list[str], global_line_offset: int) -> tuple[HL7Message | None, list[tuple[int, str]]]:
    """Parse lines belonging to a single HL7 message.
    Returns (HL7Message or None, list of non-HL7 lines with global line numbers).
    """
    non_hl7: list[tuple[int, str]] = []
    segments: list[HL7Segment] = []
    encoding_chars: dict | None = None
    message_type = ""

    for i, line in enumerate(lines):
        stripped = line.rstrip("\r\n")
        if not stripped:
            continue

        line_num = global_line_offset + i

        if stripped.startswith("MSH") and len(stripped) > 3:
            if encoding_chars is None:
                encoding_chars = _extract_encoding_chars(stripped)

            segment = _parse_segment(stripped, encoding_chars)
            segments.append(segment)

            # Extract message type from MSH.9
            fs = encoding_chars["field_sep"]
            parts = stripped.split(fs)
            if len(parts) > 8:
                message_type = parts[8]
        elif encoding_chars is not None and len(stripped) >= 3 and re.match(r"^[A-Z][A-Z0-9]{2}\|", stripped):
            # Valid segment line (3 uppercase letters/digits followed by field separator)
            segment = _parse_segment(stripped, encoding_chars)
            segments.append(segment)
        elif encoding_chars is not None and len(stripped) >= 3 and re.match(r"^[A-Z][A-Z0-9]{2}" + re.escape(encoding_chars["field_sep"]), stripped):
            segment = _parse_segment(stripped, encoding_chars)
            segments.append(segment)
        else:
            non_hl7.append((line_num, stripped))

    if not segments:
        return None, non_hl7

    raw_text = "\n".join(line.rstrip("\r\n") for line in lines if line.strip())

    return HL7Message(
        segments=segments,
        encoding_chars=encoding_chars,
        message_type=message_type,
        raw_text=raw_text,
    ), non_hl7


def parse(text: str) -> ParseResult:
    """Parse raw text containing one or more HL7 messages.

    Best-effort: never raises exceptions. Returns ParseResult with whatever
    could be parsed. Non-HL7 lines are collected separately.
    """
    if not text or not text.strip():
        return ParseResult()

    try:
        return _parse_impl(text)
    except Exception:
        # Best-effort: never throw — return everything as non-HL7
        lines = text.splitlines()
        return ParseResult(
            non_hl7_lines=[(i + 1, line) for i, line in enumerate(lines) if line.strip()],
            is_valid_hl7=False,
        )


def _parse_impl(text: str) -> ParseResult:
    """Internal implementation of parse logic."""
    lines = text.splitlines(keepends=True)

    # Find message boundaries: each message starts with a line beginning "MSH|" (or "MSH" + any char)
    message_blocks: list[tuple[int, list[str]]] = []  # (start_line_index, lines)
    current_block: list[str] = []
    current_start = 0
    pre_msh_lines: list[tuple[int, str]] = []  # non-HL7 lines before first MSH

    found_first_msh = False

    for i, line in enumerate(lines):
        stripped = line.rstrip("\r\n")
        if stripped.startswith("MSH") and len(stripped) > 3:
            if not found_first_msh:
                found_first_msh = True
            if current_block and any(l.rstrip("\r\n").startswith("MSH") for l in current_block):
                # Save previous block
                message_blocks.append((current_start, current_block))
            elif current_block:
                # Lines before any MSH — they're non-HL7
                for j, bl in enumerate(current_block):
                    s = bl.rstrip("\r\n")
                    if s.strip():
                        pre_msh_lines.append((current_start + j + 1, s))
            current_block = [line]
            current_start = i
        else:
            if not found_first_msh:
                if stripped.strip():
                    pre_msh_lines.append((i + 1, stripped))
            else:
                current_block.append(line)

    # Don't forget the last block
    if current_block and any(l.rstrip("\r\n").startswith("MSH") for l in current_block):
        message_blocks.append((current_start, current_block))

    if not message_blocks:
        # No MSH found at all
        all_non_hl7 = [(i + 1, line.rstrip("\r\n")) for i, line in enumerate(lines) if line.strip()]
        return ParseResult(non_hl7_lines=all_non_hl7, is_valid_hl7=False)

    # Parse each message block
    messages: list[HL7Message] = []
    all_non_hl7: list[tuple[int, str]] = list(pre_msh_lines)

    for start_idx, block_lines in message_blocks:
        msg, non_hl7 = _parse_single_message(block_lines, start_idx + 1)
        all_non_hl7.extend(non_hl7)
        if msg is not None:
            messages.append(msg)

    return ParseResult(
        messages=messages,
        non_hl7_lines=all_non_hl7,
        is_valid_hl7=len(messages) > 0,
    )


def tokenize_field_value(raw_value: str, encoding_chars: dict) -> list[tuple[str, str]]:
    """Tokenize a field value into (text, type) pairs for UI rendering.

    Each separator character (^, ~, &) becomes its own token so the UI can
    render individual clickable value widgets separated by styled separator labels.

    Returns list of (text, token_type) where token_type is one of:
      'value', 'component_sep', 'repetition_sep', 'subcomponent_sep'
    """
    if not raw_value:
        return [("", "value")]

    esc = encoding_chars.get("escape_char", "\\")
    cs = encoding_chars.get("component_sep", "^")
    rs = encoding_chars.get("repetition_sep", "~")
    ss = encoding_chars.get("subcomponent_sep", "&")

    protected = _protect_escapes(raw_value, esc)

    tokens: list[tuple[str, str]] = []
    current: list[str] = []

    for char in protected:
        if char == rs:
            tokens.append((_restore_escapes("".join(current), esc), "value"))
            tokens.append((rs, "repetition_sep"))
            current = []
        elif char == cs:
            tokens.append((_restore_escapes("".join(current), esc), "value"))
            tokens.append((cs, "component_sep"))
            current = []
        elif char == ss:
            tokens.append((_restore_escapes("".join(current), esc), "value"))
            tokens.append((ss, "subcomponent_sep"))
            current = []
        else:
            current.append(char)

    tokens.append((_restore_escapes("".join(current), esc), "value"))
    return tokens
