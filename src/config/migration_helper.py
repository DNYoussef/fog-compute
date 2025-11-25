"""
Migration Helper Script for Centralized Configuration

This script helps identify and report hardcoded values in the codebase that should
be migrated to use the centralized configuration module.

Usage:
    python migration_helper.py [path_to_scan]

Example:
    python migration_helper.py ../fog
    python migration_helper.py ../p2p
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple


# Patterns to detect hardcoded configuration values
PATTERNS = {
    'redis_url': r'redis://[^\s"\']+(:\d+)?',
    'localhost': r'["\']localhost["\']',
    'ip_address': r'["\']127\.0\.0\.1["\']',
    'port_3000': r'(?:port.*?=.*?|:)3000(?!\d)',
    'port_6379': r'(?:port.*?=.*?|:)6379(?!\d)',
    'port_8000': r'(?:port.*?=.*?|:)8000(?!\d)',
    'port_8080': r'(?:port.*?=.*?|:)8080(?!\d)',
    'port_8443': r'(?:port.*?=.*?|:)8443(?!\d)',
    'port_9000': r'(?:port.*?=.*?|:)9000(?!\d)',
    'circuit_hops': r'(?:hops?|num_hops).*?=.*?["\']?([3-7])["\']?(?!\d)',
    'circuit_lifetime': r'(?:lifetime|ttl).*?=.*?["\']?(\d+)["\']?',
    'reward_rate': r'reward.*?rate.*?=.*?["\']?(\d+\.?\d*)["\']?',
    'max_circuits': r'max.*?circuits.*?=.*?["\']?(\d+)["\']?',
}

# Replacement suggestions
REPLACEMENTS = {
    'redis_url': 'config.network.redis_url',
    'localhost': 'config.network.api_host or appropriate host config',
    'ip_address': 'config.network.betanet_host or appropriate host config',
    'port_3000': 'config.network.api_port (check context)',
    'port_6379': 'config.redis.port',
    'port_8000': 'config.network.bitchat_port',
    'port_8080': 'config.network.api_port or config.network.coordinator_port',
    'port_8443': 'config.network.betanet_api_port',
    'port_9000': 'config.network.betanet_port or config.betanet.server_port',
    'circuit_hops': 'config.privacy.min_circuit_hops or config.privacy.default_circuit_hops',
    'circuit_lifetime': 'config.privacy.circuit_lifetime_minutes',
    'reward_rate': 'config.tokenomics.reward_rate_per_hour',
    'max_circuits': 'config.privacy.max_circuits',
}


class MigrationAnalyzer:
    """Analyze code for hardcoded configuration values."""

    def __init__(self, root_path: Path):
        """Initialize analyzer with root path to scan.

        Args:
            root_path: Root directory to scan for Python files
        """
        self.root_path = Path(root_path)
        self.findings: List[Dict] = []

    def scan_file(self, file_path: Path) -> List[Tuple[int, str, str, str]]:
        """Scan a single file for hardcoded values.

        Args:
            file_path: Path to Python file to scan

        Returns:
            List of (line_number, pattern_name, matched_text, line_content) tuples
        """
        findings = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, start=1):
                    # Skip comments and imports
                    if line.strip().startswith('#') or 'import' in line:
                        continue

                    for pattern_name, pattern in PATTERNS.items():
                        matches = re.finditer(pattern, line, re.IGNORECASE)
                        for match in matches:
                            findings.append((
                                line_num,
                                pattern_name,
                                match.group(0),
                                line.strip()
                            ))

        except (UnicodeDecodeError, PermissionError) as e:
            print(f"Warning: Could not read {file_path}: {e}")

        return findings

    def scan_directory(self) -> None:
        """Scan directory recursively for Python files."""
        python_files = list(self.root_path.rglob('*.py'))

        print(f"Scanning {len(python_files)} Python files in {self.root_path}...")
        print()

        for file_path in python_files:
            # Skip test files and this migration script
            if 'test_' in file_path.name or file_path.name == 'migration_helper.py':
                continue

            # Skip config module itself
            if 'config' in file_path.parts and file_path.name == '__init__.py':
                continue

            file_findings = self.scan_file(file_path)
            if file_findings:
                self.findings.append({
                    'file': file_path,
                    'findings': file_findings
                })

    def generate_report(self) -> str:
        """Generate migration report.

        Returns:
            Formatted report string
        """
        if not self.findings:
            return "No hardcoded configuration values found!"

        lines = [
            "=" * 80,
            "CONFIGURATION MIGRATION REPORT",
            "=" * 80,
            "",
            f"Found hardcoded values in {len(self.findings)} files",
            "",
        ]

        # Group by priority
        high_priority = []
        medium_priority = []
        low_priority = []

        for item in self.findings:
            file_path = item['file']
            findings = item['findings']

            # Categorize by pattern type
            has_network = any(f[1] in ['redis_url', 'localhost', 'ip_address'] for f in findings)
            has_ports = any(f[1].startswith('port_') for f in findings)

            if has_network or has_ports:
                high_priority.append(item)
            elif any(f[1] in ['circuit_hops', 'circuit_lifetime', 'max_circuits'] for f in findings):
                medium_priority.append(item)
            else:
                low_priority.append(item)

        # Report high priority files
        if high_priority:
            lines.extend([
                "HIGH PRIORITY (Network addresses and ports)",
                "-" * 80,
                ""
            ])
            for item in high_priority:
                lines.extend(self._format_file_findings(item))

        # Report medium priority files
        if medium_priority:
            lines.extend([
                "",
                "MEDIUM PRIORITY (Privacy/VPN settings)",
                "-" * 80,
                ""
            ])
            for item in medium_priority:
                lines.extend(self._format_file_findings(item))

        # Report low priority files
        if low_priority:
            lines.extend([
                "",
                "LOW PRIORITY (Other settings)",
                "-" * 80,
                ""
            ])
            for item in low_priority:
                lines.extend(self._format_file_findings(item))

        # Add summary
        lines.extend([
            "",
            "=" * 80,
            "MIGRATION STEPS",
            "=" * 80,
            "",
            "1. Add import at top of file:",
            "   from config import config",
            "",
            "2. Replace hardcoded values with config references:",
        ])

        # Add unique replacements found
        unique_patterns = set()
        for item in self.findings:
            for finding in item['findings']:
                unique_patterns.add(finding[1])

        for pattern in sorted(unique_patterns):
            if pattern in REPLACEMENTS:
                lines.append(f"   - {pattern}: use {REPLACEMENTS[pattern]}")

        lines.extend([
            "",
            "3. Test thoroughly after migration",
            "",
            "4. Remove old hardcoded values",
            "",
            "See config/README.md for detailed migration guide",
            "",
        ])

        return "\n".join(lines)

    def _format_file_findings(self, item: Dict) -> List[str]:
        """Format findings for a single file.

        Args:
            item: Dictionary containing file path and findings

        Returns:
            List of formatted lines
        """
        lines = []
        file_path = item['file']
        findings = item['findings']

        lines.append(f"File: {file_path.relative_to(self.root_path.parent)}")
        lines.append(f"  Found {len(findings)} issue(s):")
        lines.append("")

        for line_num, pattern_name, matched_text, line_content in findings:
            lines.append(f"  Line {line_num}: {pattern_name}")
            lines.append(f"    Matched: {matched_text}")
            lines.append(f"    Context: {line_content[:80]}...")
            if pattern_name in REPLACEMENTS:
                lines.append(f"    Replace with: {REPLACEMENTS[pattern_name]}")
            lines.append("")

        return lines

    def save_report(self, output_path: Path) -> None:
        """Save report to file.

        Args:
            output_path: Path to save report
        """
        report = self.generate_report()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Report saved to: {output_path}")


def main():
    """Main entry point for migration helper."""
    if len(sys.argv) > 1:
        scan_path = Path(sys.argv[1])
    else:
        # Default to scanning parent directory
        scan_path = Path(__file__).parent.parent

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        sys.exit(1)

    print(f"Scanning directory: {scan_path.absolute()}")
    print()

    analyzer = MigrationAnalyzer(scan_path)
    analyzer.scan_directory()

    # Print report to console
    report = analyzer.generate_report()
    print(report)

    # Save to file
    output_path = Path(__file__).parent / 'migration_report.txt'
    analyzer.save_report(output_path)


if __name__ == '__main__':
    main()
