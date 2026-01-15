#!/usr/bin/env python3
"""
Test import script for quality_validator component.
Verifies the library component is properly installed and functional.
"""

import sys
from pathlib import Path

# Add parent directories to path for testing
tools_dir = Path(__file__).parent.parent.parent.parent
if str(tools_dir) not in sys.path:
    sys.path.insert(0, str(tools_dir))


def test_basic_import():
    """Test basic import of all components"""
    from tools.lib.validation import (
        QualityValidator,
        QualityClaim,
        QualityValidationResult,
        ValidationResult,
        Violation,
        AnalysisResult,
        EvidenceQuality,
        RiskLevel,
        Severity,
    )
    print("[PASS] All components imported successfully")
    return True


def test_validator_instantiation():
    """Test QualityValidator can be instantiated"""
    from tools.lib.validation import QualityValidator

    validator = QualityValidator()
    assert validator is not None
    assert validator.config is not None
    print("[PASS] QualityValidator instantiated successfully")
    return True


def test_add_violation():
    """Test adding violations to validator"""
    from tools.lib.validation import QualityValidator

    validator = QualityValidator()
    violation = validator.add_violation(
        rule_id="TEST-001",
        message="Test violation",
        file="test.py",
        line=10,
        severity="medium",
        category="test",
    )

    assert violation is not None
    assert violation.rule_id == "TEST-001"
    assert len(validator.violations) == 1
    print("[PASS] Violation added successfully")
    return True


def test_quality_gate():
    """Test quality gate pass/fail logic"""
    from tools.lib.validation import QualityValidator

    validator = QualityValidator()

    # Should pass with no violations
    assert validator.check_gate() is True

    # Add a medium violation - should still pass
    validator.add_violation(
        rule_id="TEST-002",
        message="Medium severity",
        file="test.py",
        line=20,
        severity="medium",
    )
    assert validator.check_gate(fail_on="high") is True

    # Add a critical violation - should fail
    validator.add_violation(
        rule_id="TEST-003",
        message="Critical severity",
        file="test.py",
        line=30,
        severity="critical",
    )
    assert validator.check_gate(fail_on="critical") is False

    print("[PASS] Quality gate logic works correctly")
    return True


def test_score_calculation():
    """Test score calculation"""
    from tools.lib.validation import QualityValidator

    validator = QualityValidator()

    # Perfect score with no violations
    assert validator.calculate_score() == 100.0

    # Add violations and check score decreases
    validator.add_violation(
        rule_id="TEST-004",
        message="High severity",
        file="test.py",
        line=40,
        severity="high",
    )
    score = validator.calculate_score()
    assert score < 100.0
    assert score == 95.0  # 100 - 5 (high penalty)

    print("[PASS] Score calculation works correctly")
    return True


def test_analysis_result():
    """Test analysis result generation"""
    from tools.lib.validation import QualityValidator

    validator = QualityValidator()
    validator.add_violation(
        rule_id="TEST-005",
        message="Test for analysis",
        file="test.py",
        line=50,
        severity="low",
    )

    result = validator.analyze(project_path="test-project")

    assert result is not None
    assert result.overall_score == 99.0  # 100 - 1 (low penalty)
    assert result.quality_gate_passed is True
    assert len(result.violations) == 1
    assert result.metadata["project_path"] == "test-project"

    print("[PASS] Analysis result generated correctly")
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("Quality Validator Component Test Suite")
    print("=" * 60)
    print()

    tests = [
        test_basic_import,
        test_validator_instantiation,
        test_add_violation,
        test_quality_gate,
        test_score_calculation,
        test_analysis_result,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
