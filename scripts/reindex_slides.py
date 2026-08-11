#!/usr/bin/env python3
"""Safely reindex framework, content, canonical SVGs, working SVGs, and receipts."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from framework_lib import page_entries, replace_slide_ids
from workflow_io import atomic_write, read_json, sha256, text_sha256, write_json
from workflow_copy_contract import visible_copy_contract


BLOCKED_STATUSES = {"Content reviewing", "Content locked", "Awaiting SVG selection"}


def content_sections(text: str) -> tuple[str, dict[str, str]]:
    matches = list(re.finditer(r"^## (S\d{2})｜.*$", text, re.MULTILINE))
    if not matches:
        return text, {}
    header = text[: matches[0].start()].rstrip() + "\n\n"
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[match.start() : end].strip() + "\n"
    return header, sections


def update_framework_metadata(text: str) -> str:
    version = re.search(r"^- Storyline version:\s*(\d+)(?:\.(\d+))?\s*$", text, re.MULTILINE)
    if version:
        major = int(version.group(1))
        minor = version.group(2)
        next_version = str(major + 1) if minor is None else f"{major}.{int(minor) + 1}"
        text = text[: version.start()] + f"- Storyline version: {next_version}" + text[version.end() :]
    return text


def snapshot_project(
    backup_root: Path,
    framework: Path,
    content: Path | None,
    svg_dir: Path | None,
    svg_working: Path | None,
    protected_input: Path | None,
    working_dir: Path | None,
) -> None:
    backup_root.mkdir(parents=True, exist_ok=False)
    shutil.copy2(framework, backup_root / framework.name)
    if content:
        shutil.copy2(content, backup_root / content.name)
    for directory in (svg_dir, svg_working, protected_input, working_dir):
        if directory:
            shutil.copytree(directory, backup_root / directory.name)


def restore_project(
    backup_root: Path,
    framework: Path,
    content: Path | None,
    svg_dir: Path | None,
    svg_working: Path | None,
    protected_input: Path | None,
    working_dir: Path | None,
) -> None:
    shutil.copy2(backup_root / framework.name, framework)
    if content:
        shutil.copy2(backup_root / content.name, content)
    for directory in (svg_dir, svg_working, protected_input, working_dir):
        if directory:
            if directory.exists():
                shutil.rmtree(directory)
            shutil.copytree(backup_root / directory.name, directory)


def refresh_nested_receipt_hashes(
    project_dir: Path,
    framework_path: Path,
    content_path: Path | None,
    working_dir: Path | None,
) -> None:
    if working_dir is None:
        return
    receipts = working_dir / "receipts"
    if not receipts.is_dir():
        return

    content_text = content_path.read_text(encoding="utf-8") if content_path else ""
    _, content_map = content_sections(content_text)
    for path in receipts.glob("S*-content.json"):
        payload = read_json(path)
        slide_id = str(payload.get("slide_id", ""))
        section = content_map.get(slide_id)
        if section:
            payload["content_sha256"] = text_sha256(section)
            write_json(path, payload)

    framework_pages = {
        page.slide_id: page for page in page_entries(framework_path.read_text(encoding="utf-8"))
    }
    packets = working_dir / "packets"
    packet_evidence: dict[str, tuple[str, str, str]] = {}
    if packets.is_dir():
        for packet in packets.glob("S*-authoring.md"):
            slide_id = packet.name.removesuffix("-authoring.md")
            packet_receipt = packets / f"{slide_id}-authoring.json"
            page = framework_pages.get(slide_id)
            if not packet_receipt.is_file() or page is None:
                continue
            payload = read_json(packet_receipt)
            section = content_map.get(slide_id, "")
            if section:
                contract = visible_copy_contract(section, slide_id)
                packet_text = packet.read_text(encoding="utf-8")
                packet_text = re.sub(
                    r"(## Machine-enforced visible copy\s*\n\s*```json\s*\n).*?(\n```)",
                    lambda match: (
                        match.group(1)
                        + json.dumps(contract, ensure_ascii=False, indent=2)
                        + match.group(2)
                    ),
                    packet_text,
                    count=1,
                    flags=re.DOTALL,
                )
                atomic_write(packet, packet_text)
                payload["visible_copy_contract"] = contract
                payload["visible_copy_contract_sha256"] = contract["contract_sha256"]
            payload.update({
                "slide_id": slide_id,
                "packet_path": str(packet.resolve()),
                "packet_sha256": sha256(packet),
                "framework_page_sha256": text_sha256(page.text),
            })
            write_json(packet_receipt, payload)
            packet_evidence[slide_id] = (
                str(packet.resolve()),
                sha256(packet),
                str(payload.get("visible_copy_contract_sha256", "")),
            )

    for path in receipts.glob("S*-*-authoring.json"):
        payload = read_json(path)
        slide_id = str(payload.get("slide_id", ""))
        if slide_id in packet_evidence and payload.get("migration") is not True:
            (
                payload["packet_path"],
                payload["packet_sha256"],
                payload["visible_copy_contract_sha256"],
            ) = packet_evidence[slide_id]
        artifact_value = payload.get("artifact_path")
        if artifact_value:
            artifact = Path(str(artifact_value))
            if not artifact.is_absolute():
                artifact = project_dir / artifact
            if artifact.is_file():
                payload["artifact_path"] = str(artifact.resolve())
                payload["artifact_sha256"] = sha256(artifact)
        write_json(path, payload)

    for path in receipts.glob("S*-protected.json"):
        payload = read_json(path)
        slide_id = str(payload.get("slide_id", ""))
        page = framework_pages.get(slide_id)
        if page:
            payload["content_scope_sha256"] = text_sha256(page.fields.get("Content scope", ""))
            canonical = project_dir / "svg_output" / f"{slide_id}.svg"
            if canonical.is_file():
                payload["canonical_sha256"] = sha256(canonical)
            source = project_dir / "protected_input" / f"{slide_id}.svg"
            if payload.get("source_kind") == "user-supplied-svg" and source.is_file():
                payload["source_sha256"] = sha256(source)
            write_json(path, payload)

    request_hashes: dict[tuple[str, str], str] = {}
    for path in list(receipts.glob("S*-R*-request.json")) + list(
        receipts.glob("S*-revision-active.json")
    ):
        payload = read_json(path)
        slide_id = str(payload.get("slide_id", ""))
        base_version = str(payload.get("base_version", ""))
        base = project_dir / "svg_working" / slide_id / f"{base_version}.svg"
        if base.is_file():
            payload["base_sha256"] = sha256(base)
        immutable = {
            key: payload.get(key)
            for key in ("slide_id", "revision_id", "base_version", "base_sha256", "note", "created_at")
        }
        request_hash = text_sha256(json.dumps(immutable, ensure_ascii=False, sort_keys=True))
        payload["request_sha256"] = request_hash
        request_hashes[(str(payload.get("slide_id", "")), str(payload.get("revision_id", "")))] = request_hash
        write_json(path, payload)

    for path in receipts.glob("S*-R*-presentation.json"):
        payload = read_json(path)
        slide_id = str(payload.get("slide_id", ""))
        revision_id = path.name.split("-")[-2]
        key = (slide_id, revision_id)
        if key in request_hashes:
            payload["request_sha256"] = request_hashes[key]
        base_version = str(payload.get("base_version", ""))
        base = project_dir / "svg_working" / slide_id / f"{base_version}.svg"
        revision = project_dir / "svg_working" / slide_id / f"{revision_id}.svg"
        if base.is_file():
            payload["base_sha256"] = sha256(base)
        if revision.is_file():
            payload["revision_sha256"] = sha256(revision)
        write_json(path, payload)

    for path in receipts.glob("S*-svg-selection.json"):
        payload = read_json(path)
        slide_id = str(payload.get("slide_id", ""))
        selected_version = str(payload.get("selected_version", ""))
        selected = project_dir / "svg_working" / slide_id / f"{selected_version}.svg"
        canonical = project_dir / "svg_output" / f"{slide_id}.svg"
        if selected.is_file():
            payload["selected_sha256"] = sha256(selected)
        if canonical.is_file():
            payload["canonical_sha256"] = sha256(canonical)
        presentation_value = payload.get("presentation_receipt")
        if presentation_value:
            presentation = Path(str(presentation_value))
            if not presentation.is_absolute():
                presentation = project_dir / presentation
            if presentation.is_file():
                payload["presentation_receipt_sha256"] = sha256(presentation)
        write_json(path, payload)

    handoff = receipts / "confirmed-export-handoff.json"
    handoff.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("framework", type=Path)
    parser.add_argument("--content", type=Path)
    parser.add_argument("--svg-dir", type=Path)
    parser.add_argument("--svg-working", type=Path)
    parser.add_argument("--protected-input", type=Path)
    parser.add_argument("--working-dir", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--transaction-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--transaction-backup", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    project_dir = args.framework.resolve().parent
    if args.content is None and (project_dir / "content.md").is_file():
        args.content = project_dir / "content.md"
    if args.svg_dir is None and (project_dir / "svg_output").is_dir():
        args.svg_dir = project_dir / "svg_output"
    if args.svg_working is None and (project_dir / "svg_working").is_dir():
        args.svg_working = project_dir / "svg_working"
    if args.protected_input is None and (project_dir / "protected_input").is_dir():
        args.protected_input = project_dir / "protected_input"
    if args.working_dir is None and (project_dir / "working").is_dir():
        args.working_dir = project_dir / "working"

    if not args.framework.is_file():
        print(f"ERROR: framework not found: {args.framework}")
        return 2
    if args.content and not args.content.is_file():
        print(f"ERROR: content file not found: {args.content}")
        return 2
    if args.svg_dir and not args.svg_dir.is_dir():
        print(f"ERROR: SVG directory not found: {args.svg_dir}")
        return 2
    if args.svg_working and not args.svg_working.is_dir():
        print(f"ERROR: SVG working directory not found: {args.svg_working}")
        return 2
    if args.protected_input and not args.protected_input.is_dir():
        print(f"ERROR: protected input directory not found: {args.protected_input}")
        return 2
    if args.working_dir and not args.working_dir.is_dir():
        print(f"ERROR: working directory not found: {args.working_dir}")
        return 2

    framework_text = args.framework.read_text(encoding="utf-8")
    pages = page_entries(framework_text)
    if not pages:
        print("ERROR: framework has no Storyline pages")
        return 1
    blocked = [page.slide_id for page in pages if page.fields.get("Status") in BLOCKED_STATUSES]
    if blocked:
        print("ERROR: finish or discard active SVG gates before reindexing: " + ", ".join(blocked))
        return 1

    mapping = {
        page.slide_id: f"S{index:02d}" for index, page in enumerate(pages, start=1)
    }
    if len(mapping) != len(pages):
        print("ERROR: duplicate Slide IDs in framework")
        return 1
    changed = {old: new for old, new in mapping.items() if old != new}
    if not args.transaction_child:
        print("Slide reindex preview:")
        for page in pages:
            marker = "change" if page.slide_id in changed else "keep"
            print(f"- {page.slide_id} -> {mapping[page.slide_id]} [{marker}] {page.title}")
    if not changed:
        if not args.transaction_child:
            print("No reindex changes are required.")
        return 0
    if not args.apply:
        print("Dry run only. Re-run with --apply after confirming this mapping.")
        return 0

    content_text = args.content.read_text(encoding="utf-8") if args.content else None
    if content_text is not None:
        header, sections = content_sections(content_text)
        unknown = sorted(set(sections) - set(mapping))
        if unknown:
            print("ERROR: content.md contains pages absent from framework: " + ", ".join(unknown))
            return 1
        ordered = [replace_slide_ids(sections[p.slide_id], mapping) for p in pages if p.slide_id in sections]
        new_content = header + "\n".join(section.rstrip() for section in ordered) + "\n"
    else:
        new_content = None

    svg_files: dict[str, Path] = {}
    if args.svg_dir:
        for item in args.svg_dir.iterdir():
            if item.name == ".DS_Store":
                continue
            if not item.is_file() or not re.fullmatch(r"S\d{2}\.svg", item.name):
                print(f"ERROR: non-canonical artifact in svg_output: {item.name}")
                return 1
            if item.stem not in mapping:
                print(f"ERROR: SVG is absent from framework: {item.name}")
                return 1
            svg_files[item.stem] = item

    protected_files: dict[str, Path] = {}
    if args.protected_input:
        for item in args.protected_input.iterdir():
            if item.name == ".DS_Store":
                continue
            if not item.is_file() or not re.fullmatch(r"S\d{2}\.svg", item.name):
                print(f"ERROR: non-canonical artifact in protected_input: {item.name}")
                return 1
            if item.stem not in mapping:
                print(f"ERROR: protected input is absent from framework: {item.name}")
                return 1
            protected_files[item.stem] = item

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    if not args.transaction_child:
        backup_root = args.framework.parent / ".reindex-backups" / timestamp
        try:
            snapshot_project(
                backup_root,
                args.framework,
                args.content,
                args.svg_dir,
                args.svg_working,
                args.protected_input,
                args.working_dir,
            )
        except OSError as exc:
            print(f"ERROR: could not create reindex backup: {exc}")
            return 1
        child = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                *sys.argv[1:],
                "--transaction-child",
                "--transaction-backup",
                str(backup_root),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if child.stdout.strip():
            print(child.stdout.rstrip())
        if child.returncode != 0:
            try:
                restore_project(
                    backup_root,
                    args.framework,
                    args.content,
                    args.svg_dir,
                    args.svg_working,
                    args.protected_input,
                    args.working_dir,
                )
            except OSError as exc:
                print(f"ERROR: reindex failed and automatic rollback also failed: {exc}")
                if child.stderr.strip():
                    print(child.stderr.rstrip())
                print(f"Manual recovery backup: {backup_root}")
                return 1
            print("ERROR: reindex failed; the project was restored automatically.")
            if child.stderr.strip():
                print(child.stderr.rstrip())
            print(f"Recovery backup retained at: {backup_root}")
            return 1
        print(f"Reindex applied transactionally. Backup: {backup_root}")
        return 0

    if (
        args.transaction_backup is None
        or not args.transaction_backup.is_dir()
        or not (args.transaction_backup / args.framework.name).is_file()
    ):
        print("ERROR: transaction child has no valid backup snapshot")
        return 2
    backup_root = args.transaction_backup

    new_framework = update_framework_metadata(replace_slide_ids(framework_text, mapping))
    atomic_write(args.framework, new_framework)
    if os.environ.get("EY_REINDEX_TEST_FAIL_AFTER") == "framework":
        raise RuntimeError("injected reindex failure after framework write")
    if args.content and new_content is not None:
        atomic_write(args.content, new_content)

    if args.svg_dir:
        staged: dict[str, Path] = {}
        for old, source in svg_files.items():
            temporary = args.svg_dir / f".reindex-{old}-{timestamp}.svg"
            source.rename(temporary)
            staged[old] = temporary
        for old, temporary in staged.items():
            destination = args.svg_dir / f"{mapping[old]}.svg"
            temporary.rename(destination)
            atomic_write(destination, replace_slide_ids(destination.read_text(encoding="utf-8"), mapping))

    if args.svg_working:
        staged_dirs: dict[str, Path] = {}
        for old in mapping:
            source = args.svg_working / old
            if source.is_dir():
                temporary = args.svg_working / f".reindex-{old}-{timestamp}"
                source.rename(temporary)
                staged_dirs[old] = temporary
        for old, temporary in staged_dirs.items():
            destination = args.svg_working / mapping[old]
            temporary.rename(destination)
            # PNGs are UI-only derivatives bound to the old Slide ID. Keep the
            # SVG candidates, but force fresh previews and receipts after a
            # structural reindex instead of rewriting their provenance.
            preview = destination / "preview"
            if preview.is_dir():
                shutil.rmtree(preview)
            for item in destination.rglob("*"):
                if item.is_file() and item.suffix.lower() in {".json", ".md", ".svg"}:
                    atomic_write(item, replace_slide_ids(item.read_text(encoding="utf-8"), mapping))

    if args.protected_input:
        staged_protected: dict[str, Path] = {}
        for old, item in protected_files.items():
            temporary = args.protected_input / f".reindex-{old}-{timestamp}.svg"
            item.rename(temporary)
            staged_protected[old] = temporary
        for old, temporary in staged_protected.items():
            destination = args.protected_input / f"{mapping[old]}.svg"
            temporary.rename(destination)
            atomic_write(destination, replace_slide_ids(destination.read_text(encoding="utf-8"), mapping))

    if args.working_dir:
        packets = args.working_dir / "packets"
        if packets.is_dir():
            staged_packets: list[tuple[Path, Path]] = []
            for item in packets.iterdir():
                if not item.is_file():
                    continue
                new_name = replace_slide_ids(item.name, mapping)
                temporary = packets / f".reindex-{len(staged_packets):04d}-{timestamp}"
                item.rename(temporary)
                staged_packets.append((temporary, packets / new_name))
            for temporary, destination in staged_packets:
                text = temporary.read_text(encoding="utf-8")
                atomic_write(destination, replace_slide_ids(text, mapping))
                temporary.unlink()
        receipts = args.working_dir / "receipts"
        if receipts.is_dir():
            staged_receipts: list[tuple[Path, Path]] = []
            for item in receipts.iterdir():
                if not item.is_file():
                    continue
                new_name = replace_slide_ids(item.name, mapping)
                temporary = receipts / f".reindex-{len(staged_receipts):04d}-{timestamp}"
                item.rename(temporary)
                staged_receipts.append((temporary, receipts / new_name))
            for temporary, destination in staged_receipts:
                text = temporary.read_text(encoding="utf-8")
                atomic_write(destination, replace_slide_ids(text, mapping))
                temporary.unlink()
        for item in args.working_dir.iterdir():
            if item.is_file() and item.suffix.lower() in {".json", ".md"}:
                atomic_write(item, replace_slide_ids(item.read_text(encoding="utf-8"), mapping))

    refresh_nested_receipt_hashes(project_dir, args.framework, args.content, args.working_dir)

    print("Reindex transaction child completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
