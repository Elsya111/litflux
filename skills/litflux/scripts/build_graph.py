#!/usr/bin/env python3
"""Build one LitFlux project module into an offline reader."""
import argparse
import json
from pathlib import Path

from semantic_authoring import build_semantic, compile_module_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path, help='Agent-authored project module (JS)')
    parser.add_argument('output', type=Path, nargs='?', default=Path('.litflux/output'),
                        help='Output directory (default: .litflux/output)')
    parser.add_argument('--source-root', type=Path, required=True, help='Project root for source verification')
    parser.add_argument('--language', choices=('en', 'zh'), default=None)
    parser.add_argument('--review', '--qa', dest='review', type=Path,
                        help='review.json written by an independent agent session')
    parser.add_argument('--draft', action='store_true', help='Build without waiting for review')
    parser.add_argument('--preflight', action='store_true', help='Check the module and sources without rendering')
    parser.add_argument('--check-only', action='store_true', help='Check current evidence without writing output')
    parser.add_argument('--no-browser', action='store_true', help='Skip the browser check; geometry stays unchecked')
    args = parser.parse_args()
    try:
        if args.preflight:
            compiled = compile_module_file(args.project.resolve(), args.source_root.resolve())
            print(json.dumps({'valid': True, 'counts': compiled['counts'],
                              'requiredNotes': compiled['requiredNotes'],
                              'boundary': compiled['boundary']}, ensure_ascii=False))
            return
        report = build_semantic(args.project, args.output, args.source_root, args.language,
                                draft=args.draft, qa_path=args.review,
                                browser=not args.no_browser, check_only=args.check_only)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(json.dumps({'valid': False, 'error': str(error)}, ensure_ascii=False))
        raise SystemExit(1)
    print(json.dumps({key: report[key] for key in
                      ('valid', 'deliveryStatus', 'counts', 'qualityRevision', 'outputs')},
                     ensure_ascii=False))
    audit = report['semanticAudit']
    if audit['errors']:
        print(json.dumps({'deliveryStatus': report['deliveryStatus'], 'errors': audit['errors'],
                          'geometry': audit.get('geometry')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
