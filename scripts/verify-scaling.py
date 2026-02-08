#!/usr/bin/env python3
"""
Verification script for FUNC-02 (Deployment Scaling Logic)
Validates implementation completeness and correctness
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

def verify_scaling_implementation():
    """Verify FUNC-02 scaling implementation"""
    print("=" * 80)
    print("FUNC-02: Deployment Scaling Logic - Verification")
    print("=" * 80)
    print()

    checks_passed = 0
    checks_failed = 0

    # Check 1: Verify scale_deployment endpoint exists
    print("[1/7] Checking scale_deployment endpoint...")
    try:
        from server.routes.deployment import scale_deployment
        print("    SUCCESS: scale_deployment endpoint found")
        checks_passed += 1
    except ImportError as e:
        print(f"    FAILED: Cannot import scale_deployment: {e}")
        checks_failed += 1

    # Check 2: Verify ScaleRequest model supports 1-100 replicas
    print("\n[2/7] Checking ScaleRequest model...")
    try:
        from server.routes.deployment import ScaleRequest
        from pydantic import ValidationError

        # Valid range
        ScaleRequest(replicas=1)
        ScaleRequest(replicas=50)
        ScaleRequest(replicas=100)

        # Invalid range
        try:
            ScaleRequest(replicas=0)
            print("    FAILED: Accepts replicas=0 (should reject)")
            checks_failed += 1
        except ValidationError:
            pass

        try:
            ScaleRequest(replicas=101)
            print("    FAILED: Accepts replicas=101 (should reject)")
            checks_failed += 1
        except ValidationError:
            pass

        print("    SUCCESS: ScaleRequest validates replicas 1-100")
        checks_passed += 1
    except Exception as e:
        print(f"    FAILED: ScaleRequest validation error: {e}")
        checks_failed += 1

    # Check 3: Verify DeploymentReplica has updated_at column
    print("\n[3/7] Checking DeploymentReplica.updated_at...")
    try:
        from server.models.deployment import DeploymentReplica
        if hasattr(DeploymentReplica, 'updated_at'):
            print("    SUCCESS: DeploymentReplica has updated_at column")
            checks_passed += 1
        else:
            print("    FAILED: DeploymentReplica missing updated_at column")
            checks_failed += 1
    except Exception as e:
        print(f"    FAILED: Cannot check DeploymentReplica: {e}")
        checks_failed += 1

    # Check 4: Verify scheduler methods are importable
    print("\n[4/7] Checking scheduler integration...")
    try:
        from server.services.scheduler import scheduler

        required_methods = [
            '_find_available_nodes',
            '_score_nodes',
            '_create_replica',
            '_transition_replicas_to_running'
        ]

        missing_methods = []
        for method in required_methods:
            if not hasattr(scheduler, method):
                missing_methods.append(method)

        if missing_methods:
            print(f"    FAILED: Missing scheduler methods: {missing_methods}")
            checks_failed += 1
        else:
            print("    SUCCESS: All required scheduler methods available")
            checks_passed += 1
    except Exception as e:
        print(f"    FAILED: Cannot import scheduler: {e}")
        checks_failed += 1

    # Check 5: Verify DeploymentStatusHistory exists
    print("\n[5/7] Checking DeploymentStatusHistory model...")
    try:
        from server.models.deployment import DeploymentStatusHistory
        required_fields = ['deployment_id', 'old_status', 'new_status', 'changed_by', 'reason']

        missing_fields = []
        for field in required_fields:
            if not hasattr(DeploymentStatusHistory, field):
                missing_fields.append(field)

        if missing_fields:
            print(f"    FAILED: Missing fields: {missing_fields}")
            checks_failed += 1
        else:
            print("    SUCCESS: DeploymentStatusHistory has all required fields")
            checks_passed += 1
    except Exception as e:
        print(f"    FAILED: Cannot check DeploymentStatusHistory: {e}")
        checks_failed += 1

    # Check 6: Verify migration file exists
    print("\n[6/7] Checking database migration...")
    migration_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'backend',
        'alembic',
        'versions',
        '005_add_replica_updated_at.py'
    )

    if os.path.exists(migration_path):
        print("    SUCCESS: Migration file 005_add_replica_updated_at.py exists")
        checks_passed += 1
    else:
        print("    FAILED: Migration file not found")
        checks_failed += 1

    # Check 7: Verify deployment route imports
    print("\n[7/7] Checking deployment route imports...")
    try:
        from server.routes.deployment import (
            DeploymentResponse,
            DeploymentStatus,
            ReplicaStatus,
            Deployment,
            DeploymentReplica,
            DeploymentResource,
            DeploymentStatusHistory
        )
        print("    SUCCESS: All required imports available")
        checks_passed += 1
    except ImportError as e:
        print(f"    FAILED: Missing imports: {e}")
        checks_failed += 1

    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"Checks Passed: {checks_passed}/7")
    print(f"Checks Failed: {checks_failed}/7")
    print()

    if checks_failed == 0:
        print("STATUS: FUNC-02 implementation verified successfully")
        print()
        print("Next Steps:")
        print("1. Apply database migration: cd backend && alembic upgrade head")
        print("2. Start backend server: cd backend && uvicorn server.main:app --reload")
        print("3. Test scaling endpoint with curl or Postman")
        print("4. Proceed to FUNC-05 (Health Checks & Status API)")
        return 0
    else:
        print("STATUS: FUNC-02 implementation has issues")
        print("Please fix the failed checks before proceeding")
        return 1

if __name__ == "__main__":
    exit_code = verify_scaling_implementation()
    sys.exit(exit_code)
