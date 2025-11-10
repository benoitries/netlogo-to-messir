#!/usr/bin/env python3
"""
Validate graphical LUCIM PlantUML rules on generated diagrams by inspecting SVG files.

Scope (graphical rules from RULES_LUCIM_PlantUML_Diagram.md):
- LDR11-SYSTEM-SHAPE: System is declared as a PlantUML participant with a rectangle shape
- LDR12-SYSTEM-COLOR: System rectangle background must be #E8C28A
- LDR13-ACTOR-SHAPE: Each actor is declared as a PlantUML participant with a rectangle shape
- LDR14-ACTOR-COLOR: Actors rectangle background must be #FFF3B3
- LDR15-ACTIVATION-BAR-INPUT-EVENT-COLOR: Activation after input event must be #C0EBFD
- LDR16-ACTIVATION-BAR-OUTPUT-EVENT-COLOR: Activation after output event must be #274364

Heuristics and limitations:
- We parse SVG (<rect>, <text>, <path>) to identify participant headers and activation bars.
- Participant headers are approximated by a <rect> having a nearby <text> label (same group or close y).
- Actors are any participants with a label not equal to exactly "System".
- Activation bars are approximated as narrow rectangles (width <= 20, height >= 16) aligned with participant x.
- We infer the expected color for activation bars from the nearest preceding message label text ("ie*" or "oe*").
- This is a best-effort static visual validation; it does not reconstruct full semantics.

Output:
- Prints a JSON summary with per-file "verdict" (bool) and "violations" (list).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Expected colors (case-insensitive, handle short vs full hex consistently)
COLOR_SYSTEM = "#E8C28A"
COLOR_ACTOR = "#FFF3B3"
COLOR_ACTIVATION_AFTER_IE = "#C0EBFD"
COLOR_ACTIVATION_AFTER_OE = "#274364"


def _norm_hex(color: Optional[str]) -> Optional[str]:
    if not isinstance(color, str):
        return None
    c = color.strip()
    # Keep only the last occurrence if style="...;fill:#HEX;..." is passed elsewhere
    return c.lower()


def _extract_style_fill(style: Optional[str]) -> Optional[str]:
    if not style:
        return None
    # style="fill:#abc123;stroke:#000000;..."
    m = re.search(r"fill\s*:\s*([^;]+)", style, flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(1).strip()


def _float(attr_val: Optional[str], default: float = 0.0) -> float:
    try:
        return float(attr_val) if attr_val is not None else default
    except ValueError:
        return default


@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float
    fill: Optional[str]
    raw_element: ET.Element

    @property
    def mid_x(self) -> float:
        return self.x + self.width / 2.0

    @property
    def mid_y(self) -> float:
        return self.y + self.height / 2.0


@dataclass
class Text:
    x: float
    y: float
    content: str
    raw_element: ET.Element


def _find_all(svg: ET.Element, tag: str) -> List[ET.Element]:
    # Plain ElementTree namespaces handling (PlantUML svg often has no explicit ns prefix)
    elements = []
    for elem in svg.iter():
        if elem.tag.endswith(tag):
            elements.append(elem)
    return elements


def _collect_rects(svg_root: ET.Element) -> List[Rect]:
    rects: List[Rect] = []
    for el in _find_all(svg_root, "rect"):
        style_fill = _extract_style_fill(el.get("style"))
        fill = el.get("fill") or style_fill
        rects.append(
            Rect(
                x=_float(el.get("x")),
                y=_float(el.get("y")),
                width=_float(el.get("width")),
                height=_float(el.get("height")),
                fill=_norm_hex(fill),
                raw_element=el,
            )
        )
    return rects


def _collect_texts(svg_root: ET.Element) -> List[Text]:
    texts: List[Text] = []
    for el in _find_all(svg_root, "text"):
        txt = "".join(el.itertext()).strip()
        # Some renderers store positions on child <tspan>
        x_attr = el.get("x")
        y_attr = el.get("y")
        if x_attr is None or y_attr is None:
            # Try first child <tspan>
            for tspan in el:
                if tspan.tag.endswith("tspan"):
                    if x_attr is None:
                        x_attr = tspan.get("x")
                    if y_attr is None:
                        y_attr = tspan.get("y")
                    if x_attr is not None and y_attr is not None:
                        break
        texts.append(
            Text(
                x=_float(x_attr),
                y=_float(y_attr),
                content=txt,
                raw_element=el,
            )
        )
    return texts


def _assign_participants(rects: List[Rect], texts: List[Text]) -> Dict[str, Rect]:
    """
    Pair a participant label text to the nearest header rectangle above/around it.
    Heuristic:
      - header rects are usually wider (> 60) and shorter (< 40)
      - choose the rect whose mid_x is closest to text.x and whose y is near text.y (|dy| < 40)
    """
    participants: Dict[str, Rect] = {}
    for t in texts:
        label = t.content.strip()
        if not label:
            continue
        # Candidate rectangles near the text
        cands: List[Tuple[float, Rect]] = []
        for r in rects:
            if r.width >= 60 and r.height <= 40:
                dy = abs((r.y + r.height / 2.0) - t.y)
                dx = abs(r.mid_x - t.x)
                if dy <= 40:
                    cands.append((dx + dy * 0.2, r))
        if not cands:
            continue
        cands.sort(key=lambda it: it[0])
        best = cands[0][1]
        # Assign if not already assigned
        if label not in participants:
            participants[label] = best
    return participants


def _find_activation_bars(rects: List[Rect], participant_rects: Dict[str, Rect]) -> List[Tuple[str, Rect]]:
    """
    Identify activation bars and associate them to the closest participant by X alignment.
    Heuristic:
      - activation bars are narrow (width <= 20) and tall (height >= 16)
      - we exclude header rectangles (height <= 40 and width >= 60 at header Y)
      - choose participant whose header mid_x is closest to bar.mid_x
    """
    bars: List[Tuple[str, Rect]] = []
    # Build participant X anchors
    anchors: List[Tuple[str, float]] = [(name, r.mid_x) for name, r in participant_rects.items()]
    for r in rects:
        if r.width <= 20 and r.height >= 16:
            # Likely an activation bar
            # Assign to participant by X proximity
            if not anchors:
                continue
            closest = min(anchors, key=lambda it: abs(it[1] - r.mid_x))
            bars.append((closest[0], r))
    return bars


def _index_message_labels(texts: List[Text]) -> List[Text]:
    """
    Extract message labels that look like 'ieSomething(...)' or 'oeSomething(...)'.
    Return sorted by Y (draw order typically top-to-bottom).
    """
    msgs: List[Text] = []
    for t in texts:
        content = t.content.replace(" ", "")
        if re.match(r"^(ie|oe)\w*\(.*\)$", content):
            msgs.append(t)
    msgs.sort(key=lambda tt: tt.y)
    return msgs


def _expected_activation_color_for_y(y_bar: float, message_texts_sorted: List[Text]) -> Optional[str]:
    """
    Heuristic: find the nearest preceding message label by Y and return the expected bar color
    (ie => C0EBFD, oe => 274364). If none is found above the bar, return None.
    """
    prev = None
    for t in message_texts_sorted:
        if t.y <= y_bar:
            prev = t
        else:
            break
    if not prev:
        return None
    content = prev.content.replace(" ", "")
    if content.startswith("ie"):
        return _norm_hex(COLOR_ACTIVATION_AFTER_IE)
    if content.startswith("oe"):
        return _norm_hex(COLOR_ACTIVATION_AFTER_OE)
    return None


def validate_svg_file(svg_path: Path) -> Dict[str, object]:
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except Exception as e:
        return {
            "file": str(svg_path),
            "verdict": False,
            "violations": [
                {
                    "id": "SVG-PARSE-ERROR",
                    "message": f"Failed to parse SVG: {e}",
                    "line": 1,
                }
            ],
        }

    rects = _collect_rects(root)
    texts = _collect_texts(root)
    participants = _assign_participants(rects, texts)
    bars = _find_activation_bars(rects, participants)
    msg_texts = _index_message_labels(texts)

    violations: List[Dict[str, object]] = []
    ok = True

    # LDR11/LDR13: participant headers must be rectangles (presence checked by assignment)
    # - We consider missing rectangle for a participant label a shape violation.
    for t in texts:
        label = t.content.strip()
        if not label:
            continue
        if label in participants:
            continue
        # Only enforce for labels that look like participant identifiers:
        # "System" or something matching theActor:ActType or a simple actor alias nearby a box
        if label == "System" or ":" in label:
            ok = False
            rule_id = "LDR11-SYSTEM-SHAPE" if label == "System" else "LDR13-ACTOR-SHAPE"
            violations.append(
                {
                    "id": rule_id,
                    "message": f"Participant '{label}' not matched to a rectangle header shape.",
                    "line": 1,
                    "extracted_values": {"label": label},
                }
            )

    # LDR12/LDR14: color checks on header rectangles
    for name, r in participants.items():
        fill = _norm_hex(r.fill)
        if name == "System":
            if fill != _norm_hex(COLOR_SYSTEM):
                ok = False
                violations.append(
                    {
                        "id": "LDR12-SYSTEM-COLOR",
                        "message": f"System rectangle must have background {COLOR_SYSTEM}.",
                        "line": 1,
                        "extracted_values": {"label": name, "found_fill": fill},
                    }
                )
        else:
            if fill != _norm_hex(COLOR_ACTOR):
                ok = False
                violations.append(
                    {
                        "id": "LDR14-ACTOR-COLOR",
                        "message": f"Actor rectangle must have background {COLOR_ACTOR}.",
                        "line": 1,
                        "extracted_values": {"label": name, "found_fill": fill},
                    }
                )

    # LDR15/LDR16: activation bar color after ie/oe
    # Heuristic: for each activation bar, find expected color from nearest preceding message label.
    for part_name, bar in bars:
        expected = _expected_activation_color_for_y(bar.mid_y, msg_texts)
        if not expected:
            # If we cannot infer, accept but note informationally if color is none
            # Skip violation to avoid false positives
            continue
        found = _norm_hex(bar.fill)
        if found != expected:
            ok = False
            violations.append(
                {
                    "id": "LDR15-16-ACTIVATION-BAR-COLOR",
                    "message": "Activation bar color does not match preceding event type (ie => #C0EBFD, oe => #274364).",
                    "line": 1,
                    "extracted_values": {
                        "participant": part_name,
                        "expected": expected,
                        "found": found,
                        "bar_bbox": {"x": bar.x, "y": bar.y, "w": bar.width, "h": bar.height},
                    },
                }
            )

    return {"file": str(svg_path), "verdict": ok and len(violations) == 0, "violations": violations}


def scan_directory(diagrams_root: Path) -> List[Dict[str, object]]:
    """
    Scan {diagrams_root}/svg for *.svg files and validate each.
    """
    svg_dir = diagrams_root / "svg"
    if not svg_dir.exists():
        svg_dir = diagrams_root
    results: List[Dict[str, object]] = []
    for path in svg_dir.rglob("*.svg"):
        results.append(validate_svg_file(path))
    return results


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate graphical LUCIM rules on PlantUML SVGs.")
    parser.add_argument(
        "diagrams_dir",
        type=str,
        help="Path to the diagrams directory (should contain an 'svg/' subfolder or be that folder).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to write full JSON report. Prints summary to stdout regardless.",
    )
    args = parser.parse_args(argv)

    root = Path(args.diagrams_dir).expanduser().resolve()
    results = scan_directory(root)

    total = len(results)
    failures = [r for r in results if not r.get("verdict", False)]
    print(f"Checked {total} SVG file(s). Failures: {len(failures)}")

    for res in results:
        status = "OK" if res["verdict"] else "FAIL"
        print(f"- {status} {res['file']}")
        if not res["verdict"]:
            for v in res["violations"]:
                rid = v.get("id")
                msg = v.get("message")
                print(f"  * {rid}: {msg}")

    if args.output:
        outp = Path(args.output).expanduser().resolve()
        outp.parent.mkdir(parents=True, exist_ok=True)
        with outp.open("w", encoding="utf-8") as f:
            json.dump({"results": results}, f, indent=2)
        print(f"Wrote full JSON report to: {outp}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())


