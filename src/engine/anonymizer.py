"""WI-005: Anonymization engine.

Replaces selected field values with a mask pattern while preserving
HL7 structure (separators ^~\\& remain intact). Empty fields stay empty.

DoD: No original value of a selected field in output.
     Output is valid HL7 (roundtrip through parser).
"""

from __future__ import annotations

from src.parser.hl7_parser import (
    HL7Field,
    HL7Segment,
    ParseResult,
    tokenize_field_value,
)


def anonymize(
    parse_result: ParseResult,
    selections: set[tuple[int, str]],
    mask: str = "***",
    length_preserve: bool = False,
    consistent: bool = False,
    message_separator: str = "\n\n",
    preserve_non_hl7: bool = False,
) -> str:
    """Anonymize selected fields in parsed HL7 messages.

    Args:
        parse_result: Parsed HL7 data from the parser.
        selections: Set of (msg_index, path) tuples identifying selected
                    components — same paths as used by ValueWidget in the UI.
        mask: Replacement string for selected values. Default: "***".
        length_preserve: WI-023 — repeat mask char to match original length.
        consistent: WI-024 — same original value → same pseudonym.
        message_separator: WI-050 — separator between messages in output. Default: blank line.
        preserve_non_hl7: WI-052 — keep non-HL7 lines at original position.

    Returns:
        Anonymized HL7 text with structure preserved.
    """
    if not parse_result.is_valid_hl7 or not parse_result.messages:
        return _rebuild_non_hl7(parse_result)

    # WI-024: consistent pseudonymization mapping
    pseudo_map: dict[str, str] = {} if consistent else {}

    message_blocks: list[str] = []

    for msg_idx, msg in enumerate(parse_result.messages):
        msg_lines: list[str] = []
        for segment in msg.segments:
            line = _anonymize_segment(
                segment, msg_idx, msg.encoding_chars, selections, mask,
                length_preserve=length_preserve,
                consistent=consistent, pseudo_map=pseudo_map,
            )
            msg_lines.append(line)
        message_blocks.append("\n".join(msg_lines))

    # WI-052: Insert non-HL7 lines at original positions
    if preserve_non_hl7 and parse_result.non_hl7_lines:
        non_hl7_text = "\n".join(content for _, content in parse_result.non_hl7_lines)
        # Place non-HL7 content between first and second message (or at end)
        if len(message_blocks) > 1:
            message_blocks.insert(1, non_hl7_text)
        else:
            message_blocks.append(non_hl7_text)

    return message_separator.join(message_blocks)


def _build_mask(mask: str, original: str, length_preserve: bool,
                 consistent: bool, pseudo_map: dict[str, str]) -> str:
    """Build the replacement string based on strategy settings."""
    if consistent:
        if original in pseudo_map:
            return pseudo_map[original]
        idx = len(pseudo_map) + 1
        pseudonym = f"ANON-{idx}"
        pseudo_map[original] = pseudonym
        return pseudonym
    if length_preserve:
        ch = mask[0] if mask else "*"
        return ch * len(original) if original else mask
    return mask


def _anonymize_segment(
    segment: HL7Segment,
    msg_idx: int,
    encoding_chars: dict,
    selections: set[tuple[int, str]],
    mask: str,
    length_preserve: bool = False,
    consistent: bool = False,
    pseudo_map: dict[str, str] | None = None,
) -> str:
    """Rebuild a segment line, replacing selected components with mask.

    Strategy: split raw_text by field separator, replace only the parts
    that contain selections, rejoin. This preserves trailing pipes,
    empty fields, and exact original formatting for untouched fields.
    """
    fs = encoding_chars.get("field_sep", "|")
    parts = segment.raw_text.split(fs)
    is_msh = segment.name == "MSH"

    fields_by_idx = {f.field_index: f for f in segment.fields}

    for field_idx, field in fields_by_idx.items():
        if field.is_empty:
            continue

        # Map field_index → index in parts[]
        # MSH: parts[0]="MSH", parts[1]=enc_chars(MSH.2), parts[2]=MSH.3, ...
        #       so MSH.N → parts[N-1]  (for N >= 2; MSH.1 is the separator itself)
        # Other: parts[0]=name, parts[1]=field1, parts[2]=field2, ...
        #       so SEG.N → parts[N]
        if is_msh:
            if field_idx == 1:
                continue  # MSH.1 is the separator — not in parts
            part_idx = field_idx - 1
        else:
            part_idx = field_idx

        if part_idx >= len(parts):
            continue

        new_value = _anonymize_field_value(
            field, msg_idx, encoding_chars, selections, mask,
            length_preserve=length_preserve,
            consistent=consistent, pseudo_map=pseudo_map,
        )
        if new_value != field.raw_value:
            parts[part_idx] = new_value

    return fs.join(parts)


def _anonymize_field_value(
    field: HL7Field,
    msg_idx: int,
    encoding_chars: dict,
    selections: set[tuple[int, str]],
    mask: str,
    length_preserve: bool = False,
    consistent: bool = False,
    pseudo_map: dict[str, str] | None = None,
) -> str:
    """Anonymize a single field value at component granularity.

    Replicates the same path-building logic as FieldGroupWidget in the UI
    so that the same (msg_index, path) keys match.
    """
    pm = pseudo_map if pseudo_map is not None else {}

    # MSH.1 / MSH.2 — treat as single selectable unit
    if field.segment_name == "MSH" and field.field_index in (1, 2):
        if (msg_idx, field.path) in selections:
            return _build_mask(mask, field.raw_value, length_preserve, consistent, pm)
        return field.raw_value

    tokens = tokenize_field_value(field.raw_value, encoding_chars)

    has_reps = any(t[1] == "repetition_sep" for t in tokens)
    has_comps = any(t[1] == "component_sep" for t in tokens)
    has_subs = any(t[1] == "subcomponent_sep" for t in tokens)
    is_simple = not has_reps and not has_comps and not has_subs

    rep, comp, sub = 1, 1, 1
    result_parts: list[str] = []

    for text, token_type in tokens:
        if token_type == "repetition_sep":
            result_parts.append(text)
            rep += 1
            comp = 1
            sub = 1
        elif token_type == "component_sep":
            result_parts.append(text)
            comp += 1
            sub = 1
        elif token_type == "subcomponent_sep":
            result_parts.append(text)
            sub += 1
        else:
            # Build path — same logic as FieldGroupWidget
            if is_simple:
                path = field.path
            else:
                path = f"{field.segment_name}.{field.field_index}"
                if has_reps:
                    path += f"({rep})"
                if has_comps or has_subs:
                    path += f".{comp}"
                if has_subs:
                    path += f".{sub}"

            if text == "":
                # Empty components stay empty (F-AO-06)
                result_parts.append(text)
            elif (msg_idx, path) in selections:
                result_parts.append(_build_mask(mask, text, length_preserve, consistent, pm))
            else:
                result_parts.append(text)

    return "".join(result_parts)


def _rebuild_non_hl7(parse_result: ParseResult) -> str:
    """For non-HL7 input, return original text unchanged."""
    return "\n".join(content for _, content in parse_result.non_hl7_lines)
