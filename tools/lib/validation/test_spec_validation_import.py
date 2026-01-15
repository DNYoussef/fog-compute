#!/usr/bin/env python3
"""
Test import script for spec_validation component.
Verifies the library component is properly installed and functional.
"""

import sys
from pathlib import Path

# Add parent directories to path for testing
tools_dir = Path(__file__).parent.parent.parent.parent
if str(tools_dir) not in sys.path:
    sys.path.insert(0, str(tools_dir))


def test_basic_import():
    """Test basic import of all SpecValidator components"""
    from tools.lib.validation import (
        SpecValidator,
        SpecValidationResult,
        ValidationSchema,
        BaseValidator,
        PrereqsValidator,
        JSONFileValidator,
        ContextValidator,
        MarkdownDocumentValidator,
        SpecDocumentValidator,
        ImplementationPlanValidator,
        validate_spec_directory,
        create_validator_from_config,
        DEFAULT_CONTEXT_SCHEMA,
        DEFAULT_IMPLEMENTATION_PLAN_SCHEMA,
        DEFAULT_SPEC_REQUIRED_SECTIONS,
        DEFAULT_SPEC_RECOMMENDED_SECTIONS,
    )
    print("[PASS] All SpecValidator components imported successfully")
    return True


def test_validation_schema():
    """Test ValidationSchema can be created and used"""
    from tools.lib.validation import ValidationSchema

    schema = ValidationSchema(
        required_fields=["name", "version"],
        optional_fields=["description"],
        allowed_values={"status": ["pending", "complete"]},
    )

    # Test valid data
    errors, warnings = schema.validate_data({"name": "test", "version": "1.0"})
    assert len(errors) == 0, f"Expected no errors, got: {errors}"

    # Test missing required field
    errors, warnings = schema.validate_data({"name": "test"})
    assert len(errors) == 1, f"Expected 1 error for missing version, got: {errors}"

    print("[PASS] ValidationSchema works correctly")
    return True


def test_spec_validation_result():
    """Test SpecValidationResult creation and methods"""
    from tools.lib.validation import SpecValidationResult

    result = SpecValidationResult(
        valid=True,
        checkpoint="test_checkpoint",
        errors=[],
        warnings=["minor warning"],
        fixes=[],
        metadata={"key": "value"},
    )

    assert result.valid is True
    assert result.checkpoint == "test_checkpoint"
    assert bool(result) is True

    # Test to_dict
    result_dict = result.to_dict()
    assert result_dict["valid"] is True
    assert result_dict["checkpoint"] == "test_checkpoint"

    # Test from_dict
    restored = SpecValidationResult.from_dict(result_dict)
    assert restored.valid == result.valid
    assert restored.checkpoint == result.checkpoint

    # Test merge
    other = SpecValidationResult(
        valid=True,
        checkpoint="other_checkpoint",
        errors=[],
        warnings=["other warning"],
    )
    merged = result.merge(other)
    assert merged.valid is True
    assert len(merged.warnings) == 2

    print("[PASS] SpecValidationResult works correctly")
    return True


def test_spec_validator_instantiation():
    """Test SpecValidator can be instantiated"""
    from tools.lib.validation import SpecValidator
    import tempfile
    import os

    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        validator = SpecValidator(spec_dir=tmpdir)
        assert validator is not None
        assert validator.spec_dir == Path(tmpdir)

    print("[PASS] SpecValidator instantiated successfully")
    return True


def test_prereqs_validator():
    """Test PrereqsValidator works"""
    from tools.lib.validation import PrereqsValidator
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        validator = PrereqsValidator(Path(tmpdir))
        result = validator.validate()

        # Directory exists, so should pass (no required files by default)
        assert result.valid is True

    print("[PASS] PrereqsValidator works correctly")
    return True


def test_default_schemas():
    """Test default schemas are accessible"""
    from tools.lib.validation import (
        DEFAULT_CONTEXT_SCHEMA,
        DEFAULT_IMPLEMENTATION_PLAN_SCHEMA,
        DEFAULT_SPEC_REQUIRED_SECTIONS,
        DEFAULT_SPEC_RECOMMENDED_SECTIONS,
    )

    assert "task_description" in DEFAULT_CONTEXT_SCHEMA.required_fields
    assert "feature" in DEFAULT_IMPLEMENTATION_PLAN_SCHEMA.required_fields
    assert "Overview" in DEFAULT_SPEC_REQUIRED_SECTIONS
    assert "Files to Modify" in DEFAULT_SPEC_RECOMMENDED_SECTIONS

    print("[PASS] Default schemas are accessible")
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("Spec Validator Component Test Suite")
    print("=" * 60)
    print()

    tests = [
        test_basic_import,
        test_validation_schema,
        test_spec_validation_result,
        test_spec_validator_instantiation,
        test_prereqs_validator,
        test_default_schemas,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
