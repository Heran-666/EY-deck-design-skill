#!/usr/bin/env python3
"""CLI adapter for the EY deck workflow authority."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from framework_lib import PageEntry, h2_section, page_entries, replace_field
from preview_renderer import PreviewError, ensure_preview_pair, ensure_preview_single
from svg_boundary import svg_error
from validate_deck_blueprint import validate as validate_blueprint
from validate_framework import validate as validate_framework
from workflow_audit import assert_current_action, audit, parse_selections
from workflow_authoring import (
    active_revision,
    author_version_for_action,
    ensure_authoring_packet,
    next_revision_id,
    page_author_completion_valid,
    page_visible_copy_contract,
    revision_advisories,
    revision_presentation_path,
    revision_presentation_valid,
    revision_request_hash,
    validate_ab,
    validate_single,
    validate_revision,
)
from workflow_content import (
    content_identity_errors,
    content_section,
    promote_provisional_content,
    provisional_content_errors,
    review_receipt_path,
)
from workflow_directives import directive, directive_payload, print_directive
from workflow_doctor import preview_failure_issue
from workflow_export import prepare_export_workspace, validate_output_filename
from workflow_handoff import output_filename
from workflow_io import atomic_write, command_line, now, read_json, sha256, text_sha256, write_json
from workflow_paths import (
    archive_items,
    handoff_result_path,
    receipt_path,
    revision_active_path,
    selected_working_path,
    working_paths,
)
from workflow_preview_evidence import (
    ab_presentation_valid,
    preview_presentation_evidence,
    single_presentation_valid,
)
from workflow_protected import materialize_protected_pages
from workflow_spec import STAGE1_ACCEPTANCE_SCHEMA, PREPARE_PPT_MASTER_ACTIONS, WORKFLOW_VERSION
from workflow_state import update_page, update_page_title
from workflow_transitions import (
    doctor_receipt_valid,
    init_agents,
    migrate_workflow,
    record_handoff_result,
    record_page_author_result,
    reopen_pages,
    repair_candidate,
    resume_handoff,
    resume_page_author,
    run_and_record_doctor,
)

@dataclass(frozen=True)
class CommandContext:
    args: argparse.Namespace
    project_dir: Path
    framework: Path
    text: str
    controller: Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('bootstrap', 'doctor', 'init', 'next', 'audit', 'prepare-ppt-master', 'prepare-export', 'validate-review', 'present-review', 'present-single', 'present-ab', 'repair-candidate', 'request-revision', 'present-revision', 'advance', 'update-page', 'set-output-filename', 'migrate', 'materialize-protected', 'ppt-master-result', 'resume-page-author', 'handoff-result', 'resume-handoff'):
        command = sub.add_parser(name)
        command.add_argument('--framework', dest='framework_option', type=Path)
        command.add_argument('--project-dir', type=Path, required=True)
        if name in {'bootstrap', 'doctor'}:
            command.add_argument('--bundled-python')
            command.add_argument('--bundle-version')
        if name == 'next':
            command.add_argument('--format', choices=('text', 'json'), default='text')
        if name == 'advance':
            command.add_argument('--event', required=True)
            command.add_argument('--page', action='append', default=[])
            command.add_argument('--selections')
            command.add_argument('--note')
            command.add_argument('--scope', choices=('content', 'design'))
        if name == 'request-revision':
            command.add_argument('--page', required=True)
            command.add_argument('--base')
            command.add_argument('--note', required=True)
        if name == 'repair-candidate':
            command.add_argument('--page', required=True)
            command.add_argument('--version', required=True)
            command.add_argument('--note', required=True)
        if name == 'update-page':
            command.add_argument('--page', required=True)
            command.add_argument('--confirmed-decisions')
            command.add_argument('--open-items')
            command.add_argument('--authoring-mode', choices=('Simplified', 'Standard'))
            command.add_argument('--title')
        if name == 'set-output-filename':
            command.add_argument('--filename', required=True)
        if name == 'prepare-ppt-master':
            command.add_argument('--page', required=True)
        if name == 'ppt-master-result':
            source = command.add_mutually_exclusive_group(required=True)
            source.add_argument('--result-json')
            source.add_argument('--result-file', type=Path)
        if name == 'resume-page-author':
            command.add_argument('--page', required=True)
            command.add_argument('--scope', choices=('content', 'design'))
            command.add_argument('--note')
        if name == 'handoff-result':
            source = command.add_mutually_exclusive_group(required=True)
            source.add_argument('--result-json')
            source.add_argument('--result-file', type=Path)
        if name == 'resume-handoff':
            command.add_argument('--page', action='append', default=[])
            command.add_argument('--note')
    return parser


def _unpack(context: CommandContext) -> tuple[argparse.Namespace, Path, Path, str, Path]:
    return (
        context.args,
        context.project_dir,
        context.framework,
        context.text,
        context.controller,
    )


def handle_migrate(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    try:
        migrated = migrate_workflow(text, project_dir)
        atomic_write(framework, migrated)
        init_agents(project_dir, controller)
        print(f'Migrated framework to workflow {WORKFLOW_VERSION}.')
        return 0
    except (ValueError, OSError) as exc:
        print(f'Migration failed: {exc}')
        return 1


def handle_reopen(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    try:
        text = reopen_pages(text, project_dir, args.page, args.scope, args.note)
        atomic_write(framework, text)
    except (OSError, ValueError) as exc:
        print(f'Transition blocked: {exc}')
        return 1
    print('Workflow state updated.')
    print_directive(text, project_dir, controller)
    return 0


def handle_repair_candidate(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    try:
        text = repair_candidate(text, project_dir, args.page, args.version, args.note)
        atomic_write(framework, text)
    except (OSError, ValueError) as exc:
        print(f'Candidate repair blocked: {exc}')
        return 1
    print(f'Reopened {args.page} {args.version} for same-slot candidate repair.')
    print_directive(text, project_dir, controller)
    return 0


def handle_doctor(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    doctor_errors, warnings = run_and_record_doctor(project_dir, args.bundled_python, args.bundle_version)
    for warning in warnings:
        print(f'WARNING: {warning}')
    if doctor_errors:
        print(f'Environment doctor failed with {len(doctor_errors)} error(s):')
        retry_arguments: list[str] = []
        if args.bundled_python:
            retry_arguments.extend(('--bundled-python', args.bundled_python))
        if args.bundle_version:
            retry_arguments.extend(('--bundle-version', args.bundle_version))
        retry_command = command_line(controller, args.command, project_dir, *retry_arguments)
        for error in doctor_errors:
            payload: dict[str, object] = dict(error)
            if error.get('code') == 'PREVIEW_BROWSER_SANDBOX_BLOCKED':
                payload.update({'retry_command': retry_command, 'approval_prefix': ['python3', str(controller)]})
            print('- ' + json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1
    print('Environment doctor passed.')
    if args.command == 'bootstrap':
        init_agents(project_dir, controller)
        print(f"Controlled workflow initialized: {project_dir / 'AGENTS.md'}")
        print_directive(text, project_dir, controller)
    return 0


def handle_init(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    if not doctor_receipt_valid(project_dir):
        print('Initialization blocked: run controller doctor successfully first.')
        return 1
    init_agents(project_dir, controller)
    print(f"Controlled workflow initialized: {project_dir / 'AGENTS.md'}")
    print_directive(text, project_dir, controller)
    return 0


def handle_audit_command(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    print('Workflow audit passed.')
    return 0


def handle_next(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    if args.format == 'json':
        print(json.dumps(directive_payload(text, project_dir, controller), ensure_ascii=False, indent=2))
    else:
        print_directive(text, project_dir, controller)
    return 0


def handle_prepare_ppt_master(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    action, selected = directive(text, project_dir)
    if action not in PREPARE_PPT_MASTER_ACTIONS or [page.slide_id for page in selected] != [args.page]:
        print(f'PPT Master preparation blocked: current action is {action}')
        return 1
    try:
        run_action = PREPARE_PPT_MASTER_ACTIONS[action]
        version = author_version_for_action(run_action, project_dir, selected[0])
        selected_working_path(project_dir, args.page, version).parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        ensure_authoring_packet(text, project_dir, selected[0])
    except (OSError, ValueError) as exc:
        print(f'PPT Master preparation failed: {exc}')
        return 1
    print(f'Locked Stage 1 packet prepared for Embedded PPT Master: {args.page}.')
    print_directive(text, project_dir, controller)
    return 0


def print_preview_blocks(
    slide_id: str,
    previews: tuple[tuple[str, str, Path], tuple[str, str, Path]],
) -> None:
    """Print local previews as standalone blocks for Codex message compatibility."""
    for version, label, png in previews:
        print(f'### {version}｜{label}\n')
        print(f'![{slide_id} {version} PNG preview](<{png}>)\n')


def handle_prepare_export(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    action, selected = directive(text, project_dir)
    if action != 'PREPARE_PPT_MASTER_EXPORT':
        print(f'Export preparation blocked: current action is {action}')
        return 1
    try:
        prepare_export_workspace(project_dir, [page.slide_id for page in selected], output_filename(text))
    except (OSError, ValueError) as exc:
        print(f'Export preparation failed: {exc}')
        return 1
    print('Confirmed export workspace prepared.')
    print_directive(text, project_dir, controller)
    return 0


def handle_validate_review(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    action, selected = directive(text, project_dir)
    if action != 'PRESENT_PAGE_REVIEW':
        print(f'Review validation blocked: current action is {action}')
        return 1
    review = project_dir / 'working' / 'provisional-content.md'
    problems = provisional_content_errors(review, selected)
    if problems:
        print(f'Provisional content validation failed with {len(problems)} error(s):')
        for problem in problems:
            print(f'- {problem}')
        return 1
    print('Provisional content validation passed for: ' + ', '.join((page.slide_id for page in selected)))
    return 0


def handle_ppt_master_result(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    try:
        raw_result = args.result_json if args.result_json is not None else args.result_file.read_text(encoding='utf-8')
        record_page_author_result(text, project_dir, raw_result)
    except (OSError, ValueError) as exc:
        print(f'Embedded PPT Master Stage 1 result rejected: {exc}')
        return 1
    print('Embedded PPT Master Stage 1 terminal result recorded.')
    print_directive(text, project_dir, controller)
    return 0


def handle_resume_page_author(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    try:
        text = resume_page_author(text, project_dir, args.page, args.scope, args.note)
        atomic_write(framework, text)
    except (OSError, ValueError) as exc:
        print(f'PPT Master Stage 1 recovery blocked: {exc}')
        return 1
    print('PPT Master Stage 1 recovery state applied.')
    print_directive(text, project_dir, controller)
    return 0


def handle_handoff_result(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    try:
        raw_result = args.result_json if args.result_json is not None else args.result_file.read_text(encoding='utf-8')
        record_handoff_result(text, project_dir, raw_result)
    except (OSError, ValueError) as exc:
        print(f'Handoff result rejected: {exc}')
        return 1
    print('Embedded PPT Master Stage 2 terminal result recorded.')
    print_directive(text, project_dir, controller)
    return 0


def handle_resume_handoff(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    try:
        text = resume_handoff(text, project_dir, args.page, args.note)
        atomic_write(framework, text)
    except (OSError, ValueError) as exc:
        print(f'Handoff recovery blocked: {exc}')
        return 1
    print('Handoff recovery state applied.')
    print_directive(text, project_dir, controller)
    return 0


def handle_materialize_protected(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    action, selected = directive(text, project_dir)
    if action != 'MATERIALIZE_PROTECTED_PAGES':
        print(f'Protected-page materialization blocked: current action is {action}')
        return 1
    try:
        materialized = materialize_protected_pages(text, project_dir)
    except (OSError, ValueError) as exc:
        print(f'Protected-page materialization failed: {exc}')
        return 1
    print('Protected canonical pages materialized: ' + ', '.join(materialized))
    print_directive(text, project_dir, controller)
    return 0


def handle_present_review(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    action, selected = directive(text, project_dir)
    if action != 'PRESENT_PAGE_REVIEW':
        print(f'Presentation blocked: current action is {action}')
        return 1
    review = project_dir / 'working' / 'provisional-content.md'
    ids = [page.slide_id for page in selected]
    problems = provisional_content_errors(review, selected)
    if problems:
        print('Provisional content presentation blocked:')
        for problem in problems:
            print(f'- {problem}')
        return 1
    write_json(review_receipt_path(project_dir, ids), {'pages': ids, 'provisional_sha256': sha256(review), 'created_at': now()})
    for page in selected:
        if page.fields.get('Status') == 'Not started':
            text = update_page(text, page.slide_id, {'Status': 'Content reviewing'})
    atomic_write(framework, text)
    print(review.read_text(encoding='utf-8').rstrip())
    print('\nAfter explicit approval, run:')
    page_args = [item for page in selected for item in ('--page', page.slide_id)]
    print(command_line(controller, 'advance', project_dir, '--event', 'content-approved', *page_args, '--note', '<EXPLICIT_APPROVAL_NOTE>'))
    return 0


def handle_present_single(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    action, selected = directive(text, project_dir)
    if action != 'PRESENT_SINGLE_OPTION':
        print(f'Single-option presentation blocked: current action is {action}')
        return 1
    packets: list[tuple[PageEntry, Path, dict[str, dict]]] = []
    for page in selected:
        if page.fields.get('Authoring mode') != 'Simplified':
            print(f'Single-option presentation blocked: {page.slide_id} is not Simplified')
            return 1
        problems, manifest = validate_single(project_dir, page.slide_id)
        if problems:
            print('Single-option presentation blocked: ' + '; '.join(problems))
            return 1
        a_path, _b_path = working_paths(project_dir, page.slide_id)
        try:
            previews = ensure_preview_single(
                project_dir,
                page.slide_id,
                'A',
                copy_contract=page_visible_copy_contract(project_dir, page.slide_id),
                prevalidated_source_hash=str((manifest or {}).get('a_sha256', '')),
            )
        except (OSError, PreviewError, ValueError) as exc:
            issue: dict[str, object] = preview_failure_issue(exc)
            issue['slide_id'] = page.slide_id
            if issue.get('repair_scope') == 'design':
                issue['repair_command'] = command_line(
                    controller, 'repair-candidate', project_dir,
                    '--page', page.slide_id, '--version', 'A',
                    '--note', '<PREVIEW_DEFECT>',
                )
            else:
                issue['retry_command'] = command_line(controller, 'present-single', project_dir)
            if issue.get('code') == 'PREVIEW_BROWSER_SANDBOX_BLOCKED':
                issue['approval_prefix'] = ['python3', str(controller)]
            print('Single-option presentation blocked: ' + json.dumps(
                issue, ensure_ascii=False, sort_keys=True
            ))
            return 1
        packets.append((page, a_path, previews))
    for page, a_path, previews in packets:
        write_json(receipt_path(project_dir, page.slide_id, 'single-presentation'), {
            'slide_id': page.slide_id,
            'authoring_mode': 'Simplified',
            'a_sha256': sha256(a_path),
            'evidence_scope': 'rendered-single-option',
            **preview_presentation_evidence(project_dir, page.slide_id, ('A',), previews),
            'created_at': now(),
        })
        text = update_page(text, page.slide_id, {'Status': 'Awaiting SVG decision'})
    atomic_write(framework, text)
    for page, a_path, previews in packets:
        a_png = project_dir / str(previews['A']['preview_png'])
        print(f'## {page.slide_id}｜Single design confirmation\n')
        print(f'![{page.slide_id} PNG preview](<{a_png}>)\n')
        print(f'Original SVG: [A.svg](<{a_path}>)\n')
        print(
            'Embedded PPT Master reports this candidate ready after its internal visual QA. '
            'Inspect the exact preview before sending it; if a visible defect remains, run '
            'repair-candidate for A. Otherwise ask the user to confirm it or request a targeted revision.\n'
        )
    return 0


def handle_present_ab(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    action, selected = directive(text, project_dir)
    if action != 'PRESENT_AB_OPTIONS':
        print(f'A/B presentation blocked: current action is {action}')
        return 1
    packets: list[tuple[PageEntry, dict, Path, Path, dict[str, dict]]] = []
    for page in selected:
        if page.fields.get('Authoring mode') != 'Standard':
            print(f'A/B presentation blocked: {page.slide_id} is not Standard')
            return 1
        problems, manifest = validate_ab(project_dir, page.slide_id)
        if problems:
            print('A/B presentation blocked: ' + '; '.join(problems))
            return 1
        a_path, b_path = working_paths(project_dir, page.slide_id)
        try:
            previews = ensure_preview_pair(project_dir, page.slide_id, ('A', 'B'), copy_contract=page_visible_copy_contract(project_dir, page.slide_id), prevalidated_source_hashes={'A': str((manifest or {}).get('a_sha256', '')), 'B': str((manifest or {}).get('b_sha256', ''))})
        except (OSError, PreviewError, ValueError) as exc:
            issue: dict[str, object] = preview_failure_issue(exc)
            issue['slide_id'] = page.slide_id
            if issue.get('repair_scope') == 'design':
                issue['repair_commands'] = {
                    version: command_line(
                        controller, 'repair-candidate', project_dir,
                        '--page', page.slide_id, '--version', version,
                        '--note', '<PREVIEW_DEFECT>',
                    )
                    for version in ('A', 'B')
                }
            else:
                issue['retry_command'] = command_line(controller, 'present-ab', project_dir)
            if issue.get('code') == 'PREVIEW_BROWSER_SANDBOX_BLOCKED':
                issue['approval_prefix'] = ['python3', str(controller)]
            print('A/B presentation blocked: ' + json.dumps(issue, ensure_ascii=False, sort_keys=True))
            return 1
        packets.append((page, manifest or {}, a_path, b_path, previews))
    for page, manifest, a_path, b_path, previews in packets:
        write_json(receipt_path(project_dir, page.slide_id, 'ab-presentation'), {'slide_id': page.slide_id, 'a_sha256': sha256(a_path), 'b_sha256': sha256(b_path), 'advisories': manifest.get('advisories', []), 'evidence_scope': 'rendered-comparison', **preview_presentation_evidence(project_dir, page.slide_id, ('A', 'B'), previews), 'created_at': now()})
        text = update_page(text, page.slide_id, {'Status': 'Awaiting SVG decision'})
    atomic_write(framework, text)
    for page, manifest, a_path, b_path, previews in packets:
        a_target = f'<{a_path}>'
        b_target = f'<{b_path}>'
        a_png = project_dir / str(previews['A']['preview_png'])
        b_png = project_dir / str(previews['B']['preview_png'])
        print(f'## {page.slide_id}｜A/B design choice\n')
        print_preview_blocks(page.slide_id, (
            ('A', 'EY option A', a_png),
            ('B', 'EY option B', b_png),
        ))
        print('Original SVG files:')
        print(f'- [A.svg]({a_target})')
        print(f'- [B.svg]({b_target})\n')
        print('Material differences:')
        differences = manifest.get('material_differences', [])
        if differences:
            for difference in differences:
                print(f'- {difference}')
        else:
            print('- Not provided (non-blocking advisory)')
        advisories = manifest.get('advisories', [])
        if advisories:
            print('\nAdvisories:')
            for advisory in advisories:
                print(f'- {advisory}')
        print(
            '\nEmbedded PPT Master reports both candidates ready after its internal visual QA. '
            'Inspect the exact previews before sending them; if either has a visible defect, run '
            'repair-candidate for that same A/B slot and do not create Rn. Otherwise send both standalone '
            'preview blocks in the same message, never place local preview images inside a Markdown table, '
            'then ask the user to choose A or B or request a targeted revision.\n'
        )
    return 0


def handle_request_revision(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    page = next((p for p in page_entries(text) if p.slide_id == args.page), None)
    if not page or page.fields.get('Status') not in {'Awaiting SVG decision', 'SVG confirmed'}:
        print(f'Revision request blocked: {args.page} is not in a decidable or confirmed SVG state')
        return 1
    if not args.note.strip():
        print('Revision request blocked: --note must record the targeted changes')
        return 1
    previous = active_revision(project_dir, args.page)
    base_version = args.base
    if not base_version and previous:
        base_version = str(previous.get('revision_id', ''))
    if not base_version and page.fields.get('Confirmed version') != 'Pending':
        base_version = page.fields.get('Confirmed version')
    if not base_version or not re.fullmatch('(?:A|B|R[1-9]\\d*)', base_version):
        print('Revision request blocked: provide a valid --base A, B, or Rn')
        return 1
    try:
        base_path = selected_working_path(project_dir, args.page, base_version)
    except ValueError as exc:
        print(f'Revision request blocked: {exc}')
        return 1
    problem = svg_error(base_path)
    if problem:
        print(f'Revision request blocked: {problem}')
        return 1
    if previous:
        previous['active'] = False
        previous['superseded_at'] = now()
        old_id = str(previous.get('revision_id', ''))
        if old_id:
            write_json(receipt_path(project_dir, args.page, f'{old_id}-request'), previous)
    revision_id = next_revision_id(project_dir, args.page)
    request = {'slide_id': args.page, 'revision_id': revision_id, 'base_version': base_version, 'base_sha256': sha256(base_path), 'note': args.note.strip(), 'active': True, 'created_at': now()}
    request['request_sha256'] = revision_request_hash(request)
    receipts_dir = project_dir / 'working' / 'receipts'
    archive_items(project_dir, args.page, [*receipts_dir.glob(f'{args.page}-R*-presentation.json')])
    write_json(receipt_path(project_dir, args.page, f'{revision_id}-request'), request)
    write_json(revision_active_path(project_dir, args.page), request)
    if page.fields.get('Status') == 'SVG confirmed':
        archive_items(project_dir, args.page, [
            project_dir / 'svg_output' / f'{args.page}.svg',
            receipt_path(project_dir, args.page, 'svg-decision'),
        ])
    text = update_page(text, args.page, {'Status': 'Awaiting SVG decision', 'Confirmed version': 'Pending'})
    atomic_write(framework, text)
    print(f'Recorded targeted revision {revision_id} for {args.page} from base {base_version}.')
    print_directive(text, project_dir, controller)
    return 0


def handle_present_revision(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    action, selected = directive(text, project_dir)
    if action != 'PRESENT_SVG_REVISION' or len(selected) != 1:
        print(f'Revision presentation blocked: current action is {action}')
        return 1
    page = selected[0]
    request = active_revision(project_dir, page.slide_id)
    if request is None:
        print('Revision presentation blocked: no active revision request')
        return 1
    problems = validate_revision(project_dir, page.slide_id, request)
    if problems:
        print('Revision presentation blocked: ' + '; '.join(problems))
        return 1
    base_version = str(request['base_version'])
    revision_id = str(request['revision_id'])
    base_path = selected_working_path(project_dir, page.slide_id, base_version)
    revision_path = selected_working_path(project_dir, page.slide_id, revision_id)
    advisories = revision_advisories(project_dir, page.slide_id, request)
    try:
        previews = ensure_preview_pair(project_dir, page.slide_id, (base_version, revision_id), copy_contract=page_visible_copy_contract(project_dir, page.slide_id), prevalidated_source_hashes={base_version: sha256(base_path), revision_id: sha256(revision_path)})
    except (OSError, PreviewError, ValueError) as exc:
        issue: dict[str, object] = preview_failure_issue(exc)
        issue.update({'slide_id': page.slide_id, 'versions': [base_version, revision_id]})
        if issue.get('repair_scope') == 'design':
            issue['repair_command'] = command_line(
                controller, 'repair-candidate', project_dir,
                '--page', page.slide_id, '--version', revision_id,
                '--note', '<PREVIEW_DEFECT>',
            )
        else:
            issue['retry_command'] = command_line(controller, 'present-revision', project_dir)
        if issue.get('code') == 'PREVIEW_BROWSER_SANDBOX_BLOCKED':
            issue['approval_prefix'] = ['python3', str(controller)]
        print('Revision presentation blocked: ' + json.dumps(issue, ensure_ascii=False, sort_keys=True))
        return 1
    write_json(revision_presentation_path(project_dir, page.slide_id, revision_id), {'slide_id': page.slide_id, 'request_sha256': request['request_sha256'], 'base_sha256': sha256(base_path), 'revision_sha256': sha256(revision_path), 'advisories': advisories, **preview_presentation_evidence(project_dir, page.slide_id, (base_version, revision_id), previews), 'created_at': now()})
    base_target = f'<{base_path}>'
    revision_target = f'<{revision_path}>'
    base_png = project_dir / str(previews[base_version]['preview_png'])
    revision_png = project_dir / str(previews[revision_id]['preview_png'])
    print(f'## {page.slide_id}｜Targeted revision review\n')
    print(f"Requested changes: {request.get('note')}\n")
    print_preview_blocks(page.slide_id, (
        (base_version, 'Base', base_png),
        (revision_id, 'Revision', revision_png),
    ))
    print('Original SVG files:')
    print(f'- [{base_version}.svg]({base_target})')
    print(f'- [{revision_id}.svg]({revision_target})\n')
    if advisories:
        print('Advisories:')
        for advisory in advisories:
            print(f'- {advisory}')
        print()
    print(
        'Required user display: send both standalone preview blocks above together in the same '
        'message. Their source PNGs have the same canvas and preserve equal scale; never place '
        'local preview images inside a Markdown table or show the revision alone.'
    )
    print(
        f'Please explicitly retain Base {base_version}, confirm Revision {revision_id}, '
        'or request another targeted revision.'
    )
    return 0


def handle_update_page(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    page = next((p for p in page_entries(text) if p.slide_id == args.page), None)
    if not page:
        print(f'Update blocked: page not found: {args.page}')
        return 1
    state = page.fields.get('Status')
    semantic_update = any((value is not None for value in (args.confirmed_decisions, args.open_items, args.title)))
    if semantic_update and state not in {'Not started', 'Content reviewing'}:
        print('Update blocked: reopen content before changing title, decisions, or open items')
        return 1
    if args.authoring_mode is not None:
        if state not in {'Not started', 'Content reviewing', 'Content locked'}:
            print('Update blocked: reopen design before changing Authoring mode')
            return 1
        page_working = project_dir / 'svg_working' / args.page
        authoring_receipts = list(
            (project_dir / 'working' / 'receipts').glob(f'{args.page}-*-authoring.json')
        )
        if page_working.exists() or authoring_receipts:
            print('Update blocked: archive existing design evidence through a design reopen first')
            return 1
    updates = {}
    if args.confirmed_decisions is not None:
        updates['Confirmed decisions'] = args.confirmed_decisions
    if args.open_items is not None:
        updates['Open items'] = args.open_items
    if args.authoring_mode is not None:
        updates['Authoring mode'] = args.authoring_mode
    if not updates and (not args.title):
        print('Update blocked: no update supplied')
        return 1
    if updates:
        text = update_page(text, args.page, updates)
    if args.title:
        text = update_page_title(text, args.page, args.title)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=framework.parent, suffix='.md', delete=False) as handle:
        handle.write(text)
        candidate_framework = Path(handle.name)
    post_errors = validate_framework(candidate_framework, project_dir)
    candidate_framework.unlink(missing_ok=True)
    if post_errors:
        print('Update produced an invalid framework: ' + '; '.join(post_errors))
        return 1
    atomic_write(framework, text)
    print(f'Updated {args.page}.')
    print_directive(text, project_dir, controller)
    return 0


def handle_set_output_filename(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    try:
        filename = validate_output_filename(args.filename)
        current = h2_section(text, 'Current position')
        updated = replace_field(current, 'Output filename', filename)
        candidate = text.replace(current, updated, 1)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=framework.parent, suffix='.md', delete=False) as handle:
            handle.write(candidate)
            candidate_framework = Path(handle.name)
        problems = validate_framework(candidate_framework, project_dir)
        candidate_framework.unlink(missing_ok=True)
        if problems:
            raise ValueError('; '.join(problems))
        archive_items(project_dir, 'output-filename', [handoff_result_path(project_dir)])
        atomic_write(framework, candidate)
    except (OSError, ValueError) as exc:
        print(f'Output filename update blocked: {exc}')
        return 1
    print(f'Output filename updated: {filename}')
    print_directive(candidate, project_dir, controller)
    return 0


def handle_advance(context: CommandContext) -> int:
    args, project_dir, framework, text, controller = _unpack(context)
    event = args.event
    review_to_clear: Path | None = None
    cleanup_warning: str | None = None
    try:
        current_action, _ = directive(text, project_dir)
        selected = assert_current_action(text, project_dir, event, args.page)
        ids = [page.slide_id for page in selected]
        if event == 'content-approved':
            if not args.note:
                raise ValueError('content-approved requires --note recording the explicit user approval')
            review = project_dir / 'working' / 'provisional-content.md'
            receipt = review_receipt_path(project_dir, ids)
            if not receipt.is_file() or read_json(receipt).get('provisional_sha256') != sha256(review):
                raise ValueError('provisional content was not presented through present-review or changed afterward')
            content_path = project_dir / 'content.md'
            provisional = review.read_text(encoding='utf-8')
            problems = provisional_content_errors(review, selected)
            if problems:
                raise ValueError('provisional build-spec validation failed: ' + '; '.join(problems))
            existing = content_path.read_text(encoding='utf-8') if content_path.is_file() else ''
            content = promote_provisional_content(text, existing, provisional)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=project_dir, suffix='.md', delete=False) as handle:
                handle.write(content)
                candidate_content = Path(handle.name)
            for slide_id, page in zip(ids, selected):
                problems = validate_blueprint(candidate_content, slide_id)
                section = content_section(content, slide_id)
                problems.extend(content_identity_errors(page, section))
                if problems:
                    candidate_content.unlink(missing_ok=True)
                    raise ValueError(f'{slide_id} build-spec validation failed: ' + '; '.join(problems))
            candidate_content.unlink(missing_ok=True)
            atomic_write(content_path, content)
            for slide_id, page in zip(ids, selected):
                section = content_section(content, slide_id)
                write_json(receipt_path(project_dir, slide_id, 'content'), {'slide_id': slide_id, 'content_sha256': text_sha256(section), 'approval_note': args.note, 'created_at': now()})
                text = update_page(text, slide_id, {'Status': 'Content locked', 'Open items': 'None'})
                title_match = re.search('^- Title:\\s*(.+)$', section, re.MULTILINE)
                if title_match:
                    text = update_page_title(text, slide_id, title_match.group(1).strip())
            review_to_clear = review
        elif event == 'svg-confirmed':
            selections = parse_selections(args.selections)
            if set(selections) != set(ids):
                raise ValueError('explicit confirmations must cover exactly the active pages')
            for slide_id, page in zip(ids, selected):
                mode = page.fields.get('Authoring mode')
                presentation_file = receipt_path(
                    project_dir,
                    slide_id,
                    'single-presentation' if mode == 'Simplified' else 'ab-presentation',
                )
                if current_action == 'COLLECT_SVG_DECISION':
                    if mode == 'Simplified':
                        if selections[slide_id] != 'A':
                            raise ValueError(f'{slide_id} Simplified confirmation must use A')
                        if not single_presentation_valid(project_dir, slide_id):
                            raise ValueError(
                                f'{slide_id} single option was not presented or changed afterward'
                            )
                    else:
                        if selections[slide_id] not in {'A', 'B'}:
                            raise ValueError(f'{slide_id} Standard selection must be A or B')
                        if not ab_presentation_valid(project_dir, slide_id):
                            raise ValueError(
                                f'{slide_id} A/B options were not presented or changed afterward'
                            )
                if current_action == 'COLLECT_REVISION_CONFIRMATION':
                    request = active_revision(project_dir, slide_id)
                    if request is None:
                        raise ValueError(f'{slide_id} has no active revision to resolve')
                    base_version = str(request.get('base_version', ''))
                    revision_id = str(request.get('revision_id', ''))
                    allowed_selections = {base_version, revision_id}
                    if selections[slide_id] not in allowed_selections:
                        raise ValueError(
                            f'{slide_id} must select the displayed Base {base_version} or '
                            f'active Revision {revision_id}'
                        )
                    if not revision_presentation_valid(project_dir, slide_id, request):
                        raise ValueError(f'{slide_id} revision was not presented or changed afterward')
                    request['active'] = False
                    request['resolved_at'] = now()
                    request['resolution'] = (
                        'base-retained'
                        if selections[slide_id] == base_version
                        else 'revision-confirmed'
                    )
                    request['selected_version'] = selections[slide_id]
                    if selections[slide_id] == revision_id:
                        request['confirmed_at'] = request['resolved_at']
                    write_json(receipt_path(project_dir, slide_id, f'{revision_id}-request'), request)
                    write_json(revision_active_path(project_dir, slide_id), request)
                    presentation_file = revision_presentation_path(project_dir, slide_id, revision_id)
                confirmed_path = selected_working_path(project_dir, slide_id, selections[slide_id])
                if not page_author_completion_valid(project_dir, slide_id, selections[slide_id]):
                    raise ValueError(f'{slide_id} confirmed SVG has no valid hash-bound Stage 1 acceptance receipt')
                if not presentation_file.is_file():
                    raise ValueError(f'{slide_id} has no presentation receipt')
                final_path = project_dir / 'svg_output' / f'{slide_id}.svg'
                final_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(confirmed_path, final_path)
                write_json(receipt_path(project_dir, slide_id, 'svg-decision'), {
                    'slide_id': slide_id,
                    'authoring_mode': mode,
                    'confirmed_version': selections[slide_id],
                    'confirmed_sha256': sha256(confirmed_path),
                    'presentation_receipt': str(presentation_file.relative_to(project_dir)),
                    'presentation_receipt_sha256': sha256(presentation_file),
                    'canonical_sha256': sha256(final_path),
                    'source_acceptance_gate': STAGE1_ACCEPTANCE_SCHEMA,
                    'accepted_at': now(),
                })
                text = update_page(text, slide_id, {
                    'Status': 'SVG confirmed',
                    'Confirmed version': selections[slide_id],
                })
        else:
            raise ValueError(f'unsupported event: {event}')
        atomic_write(framework, text)
        if review_to_clear is not None:
            try:
                review_to_clear.unlink(missing_ok=True)
            except OSError as exc:
                cleanup_warning = str(exc)
    except (ValueError, OSError) as exc:
        print(f'Transition blocked: {exc}')
        return 1
    print(f'Workflow advanced with event: {event}')
    if cleanup_warning:
        print('WARNING: approved content was committed, but provisional-content cleanup failed: ' + cleanup_warning)
    print_directive(text, project_dir, controller)
    return 0


COMMAND_HANDLERS = {
    "repair-candidate": handle_repair_candidate,
    "bootstrap": handle_doctor,
    "doctor": handle_doctor,
    "init": handle_init,
    "audit": handle_audit_command,
    "next": handle_next,
    "prepare-ppt-master": handle_prepare_ppt_master,
    "prepare-export": handle_prepare_export,
    "validate-review": handle_validate_review,
    "ppt-master-result": handle_ppt_master_result,
    "resume-page-author": handle_resume_page_author,
    "handoff-result": handle_handoff_result,
    "resume-handoff": handle_resume_handoff,
    "materialize-protected": handle_materialize_protected,
    "present-review": handle_present_review,
    "present-single": handle_present_single,
    "present-ab": handle_present_ab,
    "request-revision": handle_request_revision,
    "present-revision": handle_present_revision,
    "update-page": handle_update_page,
    "set-output-filename": handle_set_output_filename,
    "advance": handle_advance,
}


def main(controller_path: Path | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args()
    project_dir = args.project_dir.resolve()
    framework_arg = args.framework_option or Path("framework.md")
    framework = (
        framework_arg if framework_arg.is_absolute() else project_dir / framework_arg
    ).resolve()
    try:
        framework.relative_to(project_dir)
    except ValueError:
        print("ERROR: framework.md must be inside the project directory")
        return 2
    if not framework.is_file():
        print(f"ERROR: framework not found: {framework}")
        return 2
    context = CommandContext(
        args=args,
        project_dir=project_dir,
        framework=framework,
        text=framework.read_text(encoding="utf-8"),
        controller=(controller_path or Path(__file__).resolve()).resolve(),
    )

    if args.command == "migrate":
        return handle_migrate(context)
    if args.command == "advance" and args.event == "reopen":
        return handle_reopen(context)

    errors = audit(context.text, context.framework, context.project_dir)
    if errors:
        print(f"Workflow blocked by {len(errors)} audit error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    handler = COMMAND_HANDLERS[args.command]
    return handler(context)
