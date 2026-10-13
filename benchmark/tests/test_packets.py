"""Tests of rater packets and the ratings importer (SYNTHETIC rewrites and ratings)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from rbbench.claims import Claim, Method, decompose
from rbbench.packets.build import PacketError, build_packets, embed_json
from rbbench.packets.importer import RatingsImportError, import_ratings, load_key
from rbbench.rewrite.harness import RewriteRecord
from rbbench.rewrite.markup import parse_rewrite
from rbbench.rubric import Rubric, Unit

HOSTILE = "</script><script>alert(1)</script>"
SYNTHETIC_ATTRIBUTION = {"synthetic": "SYNTHETIC source text written for the tests; no licence."}


def _synthetic_rewrite(arm: str) -> RewriteRecord:
    """A SYNTHETIC rewrite whose source text contains a script-breaking string."""
    output = '<rewrite id="p1">Synthetic finding. <added>Synthetic context.</added></rewrite>'
    return RewriteRecord(
        rewrite_id=f"synthetic:passage|{arm}|1",
        passage_id="synthetic:passage",
        paper_key="synthetic",
        arm=arm,
        requested_model="fake-deterministic",
        model="fake-deterministic",
        prompt_version="rewrite_v1",
        prompt_sha256="0" * 64,
        temperature=None,
        timestamp="2026-10-13T00:00:00Z",
        synthetic=True,
        valid=True,
        errors=(),
        warnings=(),
        paragraphs=parse_rewrite(output, ["p1"]).paragraphs,
        source=(("p1", f"Synthetic source paragraph {HOSTILE}"),),
        raw_output=output,
        stop_reason="end_turn",
        input_tokens=0,
        output_tokens=0,
    )


def _inputs() -> tuple[list[RewriteRecord], list[Claim]]:
    """Two SYNTHETIC rewrites (two arms) and their sentence claims."""
    rewrites = [_synthetic_rewrite("temperature-0"), _synthetic_rewrite("default")]
    claims = [c for r in rewrites for c in decompose(r, Method.SENTENCES)]
    return rewrites, claims


@pytest.fixture
def packets(tmp_path: Path, rubric: Rubric) -> Path:
    """Build packets for two synthetic raters and return their directory."""
    rewrites, claims = _inputs()
    build_packets(
        rewrites,
        claims,
        rubric,
        ["synthetic-r1", "synthetic-r2"],
        tmp_path,
        packet_id="synthetic-packet",
        attributions=SYNTHETIC_ATTRIBUTION,
        titles={"synthetic": "A synthetic paper"},
    )
    return tmp_path


def _export(packet: dict[str, object], *, skip_last: bool = False) -> dict[str, object]:
    """Answer every code with its first value, as a SYNTHETIC rater would."""
    rubric = packet["rubric"]
    assert isinstance(rubric, dict)
    ratings = []
    items = packet["items"]
    assert isinstance(items, list)
    for item in items:
        for paragraph in item["paragraphs"]:
            units = [("claim", c["unit_id"]) for c in paragraph["claims"]]
            units.append(("paragraph", paragraph["unit_id"]))
            for unit, unit_id in units:
                labels = {
                    c["id"]: c["values"][0]["id"] for c in rubric["codes"] if c["unit"] == unit
                }
                ratings.append({"unit": unit, "unit_id": unit_id, "labels": labels, "comment": ""})
    if skip_last:
        ratings.pop()
    return {
        "format": "rbbench-ratings/1",
        "packet_id": packet["packet_id"],
        "rater_id": packet["rater_id"],
        "rubric_id": rubric["id"],
        "rubric_sha256": rubric["sha256"],
        "ratings": ratings,
    }


def test_packets_are_blinded_and_self_contained(packets: Path) -> None:
    """Rater files carry no arm, model or rewrite ID, and no network references."""
    html = (packets / "synthetic-r1.html").read_text(encoding="utf-8")
    data = (packets / "synthetic-r1.packet.json").read_text(encoding="utf-8")
    for leaked in ("temperature-0", "fake-deterministic", "synthetic:passage|"):
        assert leaked not in html
        assert leaked not in data
    assert "Content-Security-Policy" in html
    assert "default-src 'none'" in html
    assert not re.search(r"(src|href)=\"https?:", html)
    # The hostile string is present in the data but cannot close the script element.
    assert HOSTILE not in html
    assert "\\u003c/script\\u003e" in html
    assert "SYNTHETIC DRY RUN" in data
    key = json.loads((packets / "key.json").read_text(encoding="utf-8"))
    arms = {entry["arm"] for entry in key["units"].values()}
    assert arms == {"temperature-0", "default"}


def test_each_rater_gets_a_seeded_order(tmp_path: Path, rubric: Rubric) -> None:
    """Orders are reproducible per rater (same seed, same order)."""
    rewrites, claims = _inputs()
    raters = [f"synthetic-r{i}" for i in range(6)]

    def orders(directory: Path) -> list[list[str]]:
        """Build packets and return each rater's first-paragraph unit order."""
        build_packets(
            rewrites,
            claims,
            rubric,
            raters,
            directory,
            packet_id="synthetic",
            attributions=SYNTHETIC_ATTRIBUTION,
        )
        return [
            [
                item["paragraphs"][0]["unit_id"]
                for item in json.loads(
                    (directory / f"{r}.packet.json").read_text(encoding="utf-8")
                )["items"]
            ]
            for r in raters
        ]

    first, second = orders(tmp_path / "a"), orders(tmp_path / "b")
    assert first == second
    assert len({tuple(order) for order in first}) == 2


def test_import_maps_opaque_ids_back(packets: Path, rubric: Rubric) -> None:
    """A complete export imports into ratings keyed by the real unit IDs."""
    packet = json.loads((packets / "synthetic-r1.packet.json").read_text(encoding="utf-8"))
    path = packets / "r1.ratings.json"
    path.write_text(json.dumps(_export(packet)), encoding="utf-8")
    ratings = import_ratings(path, load_key(packets / "key.json"), rubric)
    claims = [r for r in ratings if r.unit is Unit.CLAIM]
    assert {r.unit_id for r in claims} == {
        "synthetic:passage|temperature-0|1#p1#c1",
        "synthetic:passage|temperature-0|1#p1#c2",
        "synthetic:passage|default|1#p1#c1",
        "synthetic:passage|default|1#p1#c2",
    }
    assert all(r.synthetic and r.rater_id == "synthetic-r1" for r in ratings)
    assert all(r.packet_id == "synthetic-packet" for r in ratings)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda e: e.update(packet_id="other"), "packet"),
        (lambda e: e.update(rater_id="intruder"), "not in the packet key"),
        (lambda e: e.update(rubric_sha256="0" * 64), "different rubric"),
        (lambda e: e["ratings"].append(dict(e["ratings"][0])), "rated twice"),
        (lambda e: e["ratings"][0].update(unit_id="c-unknown"), "unknown unit"),
        (lambda e: e["ratings"][0]["labels"].update(support="maybe"), "maybe"),
    ],
)
def test_import_rejects_mismatches(
    packets: Path, rubric: Rubric, mutate: object, message: str
) -> None:
    """Every mismatch with the packet or the rubric is refused."""
    packet = json.loads((packets / "synthetic-r1.packet.json").read_text(encoding="utf-8"))
    export = _export(packet)
    mutate(export)  # type: ignore[operator]
    path = packets / "bad.ratings.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    with pytest.raises(RatingsImportError, match=message):
        import_ratings(path, load_key(packets / "key.json"), rubric)


def test_incomplete_export_needs_explicit_permission(packets: Path, rubric: Rubric) -> None:
    """Partial exports are refused unless allowed; then missing units are skipped."""
    packet = json.loads((packets / "synthetic-r2.packet.json").read_text(encoding="utf-8"))
    path = packets / "partial.ratings.json"
    path.write_text(json.dumps(_export(packet, skip_last=True)), encoding="utf-8")
    key = load_key(packets / "key.json")
    with pytest.raises(RatingsImportError, match="unrated or incomplete"):
        import_ratings(path, key, rubric)
    assert len(import_ratings(path, key, rubric, allow_incomplete=True)) == len(key["units"]) - 1


def test_build_refuses_invalid_inputs(tmp_path: Path, rubric: Rubric) -> None:
    """No raters, duplicate raters or claimless paragraphs are refused."""
    rewrites, claims = _inputs()
    attributions = SYNTHETIC_ATTRIBUTION
    with pytest.raises(PacketError):
        build_packets(
            rewrites, claims, rubric, [], tmp_path, packet_id="x", attributions=attributions
        )
    with pytest.raises(PacketError):
        build_packets(
            rewrites, claims, rubric, ["a", "a"], tmp_path, packet_id="x", attributions=attributions
        )
    with pytest.raises(PacketError, match="no claims"):
        build_packets(
            rewrites, [], rubric, ["a"], tmp_path, packet_id="x", attributions=attributions
        )


@pytest.mark.parametrize("rater_id", ["../escaped-rater", "a/b", "a b", "", ".hidden", "r1\\x"])
def test_unsafe_rater_ids_are_refused_before_writing(
    tmp_path: Path, rubric: Rubric, rater_id: str
) -> None:
    """A rater ID that is not a plain file name is refused and nothing is written."""
    rewrites, claims = _inputs()
    out = tmp_path / "out"
    with pytest.raises(PacketError, match="rater IDs may use only"):
        build_packets(
            rewrites,
            claims,
            rubric,
            ["synthetic-ok", rater_id],
            out,
            packet_id="x",
            attributions=SYNTHETIC_ATTRIBUTION,
        )
    assert not out.exists()
    assert list(tmp_path.iterdir()) == []


def test_source_text_without_attribution_is_refused(tmp_path: Path, rubric: Rubric) -> None:
    """Packets reproduce source text, so a paper without an attribution line is refused."""
    rewrites, claims = _inputs()
    for attributions in ({}, {"synthetic": ""}):
        with pytest.raises(PacketError, match="no attribution for source text of: synthetic"):
            build_packets(
                rewrites, claims, rubric, ["a"], tmp_path, packet_id="x", attributions=attributions
            )


def test_attribution_is_shown_with_every_item(packets: Path) -> None:
    """Each item carries its paper's attribution line."""
    packet = json.loads((packets / "synthetic-r1.packet.json").read_text(encoding="utf-8"))
    assert {item["attribution"] for item in packet["items"]} == set(SYNTHETIC_ATTRIBUTION.values())


def test_embed_json_escapes_markup() -> None:
    """Angle brackets and ampersands are escaped; the JSON still decodes."""
    text = embed_json({"t": "a</script>&b"})
    assert "<" not in text
    assert "&" not in text
    assert json.loads(text) == {"t": "a</script>&b"}


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_browser_export_logic_round_trips_through_importer(
    packets: Path, rubric: Rubric, tmp_path: Path
) -> None:
    """The form's own buildExport (run in Node) produces an importable export."""
    html = (packets / "synthetic-r1.html").read_text(encoding="utf-8")
    logic = re.search(r'<script id="rbbench-logic">(.*?)</script>', html, re.DOTALL)
    assert logic is not None
    (tmp_path / "logic.js").write_text(logic.group(1), encoding="utf-8")
    runner = tmp_path / "run.js"
    runner.write_text(
        "const logic = require(process.argv[2]);\n"
        "const packet = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));\n"
        "const state = {};\n"
        "for (const {unit, unitId} of logic.listUnits(packet)) {\n"
        "  const labels = {};\n"
        "  for (const code of logic.codesFor(packet, unit)) labels[code.id] = code.values[0].id;\n"
        "  state[unitId] = {labels, comment: 'synthetic'};\n"
        "}\n"
        "const partial = logic.buildExport(packet, {}, 'now');\n"
        "if (partial.complete || logic.missingUnits(packet, {}).length === 0) process.exit(3);\n"
        "process.stdout.write(JSON.stringify(logic.buildExport(packet, state, 'now')));\n",
        encoding="utf-8",
    )
    node = shutil.which("node")
    assert node is not None
    result = subprocess.run(  # noqa: S603 - fixed arguments, files we just wrote
        [node, str(runner), str(tmp_path / "logic.js"), str(packets / "synthetic-r1.packet.json")],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    export = json.loads(result.stdout)
    assert export["complete"] is True
    path = tmp_path / "node.ratings.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    ratings = import_ratings(path, load_key(packets / "key.json"), rubric)
    assert len(ratings) == 6
    assert {r.comment for r in ratings} == {"synthetic"}


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_form_renders_and_exports_under_a_dom_stub(packets: Path) -> None:
    """The form's DOM code runs: every question renders, answering all completes it."""
    node = shutil.which("node")
    assert node is not None
    runner = Path(__file__).parent / "js" / "dom_stub_runner.js"
    result = subprocess.run(  # noqa: S603 - fixed arguments, committed runner
        [node, str(runner), str(packets / "synthetic-r1.html")],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    summary = json.loads(result.stdout)
    # 2 rewrites x 1 paragraph: 2 claims x 9 codes + 1 paragraph code, per rewrite.
    assert summary["groups"] == 2 * (2 * 9 + 1)
    assert summary["radios"] == 2 * (2 * (3 + 7 * 2 + 3) + 2)
    assert summary["before"] == "0 of 6 done"
    assert summary["after"] == "6 of 6 done"
    assert summary["status"].startswith("Exported. Thank you")
    assert summary["marks"] == 2
