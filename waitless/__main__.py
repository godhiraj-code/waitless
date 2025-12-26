"""
CLI entry point for waitless.

Provides the 'waitless doctor' command for diagnostics.
"""

import argparse
import sys
import json
from datetime import datetime


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='waitless',
        description='Waitless - Zero-wait UI automation stabilization'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Doctor command
    doctor_parser = subparsers.add_parser(
        'doctor',
        help='Analyze and diagnose stability issues'
    )
    doctor_parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format for CI integration'
    )
    doctor_parser.add_argument(
        '--file',
        type=str,
        help='Load diagnostics from a JSON file'
    )
    
    # Version command
    subparsers.add_parser('version', help='Show version')
    
    args = parser.parse_args()
    
    if args.command == 'version':
        from . import __version__
        print(f"waitless version {__version__}")
        return 0
    
    elif args.command == 'doctor':
        return run_doctor(args)
    
    else:
        parser.print_help()
        return 0


def run_doctor(args):
    """Run the doctor diagnostic command."""
    from .diagnostics import DiagnosticReport
    
    if args.file:
        # Load from file
        try:
            with open(args.file, 'r') as f:
                data = json.load(f)
            diagnostics = data.get('diagnostics', data)
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            return 1
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON: {e}", file=sys.stderr)
            return 1
    else:
        # Show usage instructions
        print("+-" + "-" * 66 + "-+")
        print("|" + "WAITLESS DOCTOR".center(66) + "|")
        print("+-" + "-" * 66 + "-+")
        print("|".ljust(67) + "|")
        print("| The doctor command analyzes stability diagnostics.".ljust(67) + "|")
        print("|".ljust(67) + "|")
        print("| USAGE OPTIONS:".ljust(67) + "|")
        print("|".ljust(67) + "|")
        print("| 1. From a diagnostic file:".ljust(67) + "|")
        print("|    waitless doctor --file diagnostics.json".ljust(67) + "|")
        print("|".ljust(67) + "|")
        print("| 2. In your test code, capture diagnostics on failure:".ljust(67) + "|")
        print("|".ljust(67) + "|")
        print("|    from waitless import get_diagnostics".ljust(67) + "|")
        print("|    from waitless.diagnostics import print_report".ljust(67) + "|")
        print("|".ljust(67) + "|")
        print("|    try:".ljust(67) + "|")
        print("|        driver.find_element(...).click()".ljust(67) + "|")
        print("|    except StabilizationTimeout as e:".ljust(67) + "|")
        print("|        print_report(engine)  # Print diagnostic report".ljust(67) + "|")
        print("|".ljust(67) + "|")
        print("| 3. Export diagnostics for CI:".ljust(67) + "|")
        print("|".ljust(67) + "|")
        print("|    diagnostics = get_diagnostics(driver)".ljust(67) + "|")
        print("|    with open('diag.json', 'w') as f:".ljust(67) + "|")
        print("|        json.dump(diagnostics, f)".ljust(67) + "|")
        print("|".ljust(67) + "|")
        print("+-" + "-" * 66 + "-+")
        return 0
    
    # Generate report
    report = DiagnosticReport(diagnostics)
    
    if args.json:
        print(report.to_json())
    else:
        print(report.generate_text_report())
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
