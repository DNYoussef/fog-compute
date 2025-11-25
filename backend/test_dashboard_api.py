"""
Quick validation script for dashboard API fix (MOCK-04)
Tests that all expected fields are present in the response
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from server.routes.dashboard import get_dashboard_stats


async def validate_dashboard_response():
    """Validate dashboard API returns all expected sections and fields"""
    print("Testing dashboard API response...")
    print("-" * 60)

    try:
        response = await get_dashboard_stats()

        # Required sections
        required_sections = ["betanet", "bitchat", "benchmarks", "idle", "tokenomics", "privacy"]

        print("\nSection Validation:")
        for section in required_sections:
            exists = section in response
            status = "PASS" if exists else "FAIL"
            print(f"  [{status}] {section}: {'present' if exists else 'MISSING'}")

        # Required fields in benchmarks
        required_benchmarks = ["avgLatency", "throughput", "networkUtilization", "cpuUsage", "memoryUsage"]

        print("\nBenchmarks Field Validation:")
        if "benchmarks" in response:
            for field in required_benchmarks:
                exists = field in response["benchmarks"]
                status = "PASS" if exists else "FAIL"
                value = response["benchmarks"].get(field, "N/A")
                print(f"  [{status}] {field}: {value}")
        else:
            print("  [FAIL] benchmarks section missing")

        # Check for data drop (all sections should exist)
        all_sections_present = all(section in response for section in required_sections)
        all_benchmarks_present = all(field in response.get("benchmarks", {}) for field in required_benchmarks)

        print("\n" + "=" * 60)
        if all_sections_present and all_benchmarks_present:
            print("VALIDATION PASSED: No data drop detected")
            print("All sections returned:", ", ".join(required_sections))
            return True
        else:
            print("VALIDATION FAILED: Data drop detected")
            missing_sections = [s for s in required_sections if s not in response]
            if missing_sections:
                print("Missing sections:", ", ".join(missing_sections))
            missing_benchmarks = [f for f in required_benchmarks if f not in response.get("benchmarks", {})]
            if missing_benchmarks:
                print("Missing benchmark fields:", ", ".join(missing_benchmarks))
            return False

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_response_structure(response):
    """Validate response structure matches documented schema"""
    print("\n" + "=" * 60)
    print("Response Structure:")
    print("=" * 60)

    for section, data in response.items():
        print(f"\n{section}:")
        if isinstance(data, dict):
            for key, value in data.items():
                value_type = type(value).__name__
                print(f"  {key}: {value} ({value_type})")
        else:
            print(f"  {data}")


if __name__ == "__main__":
    asyncio.run(validate_dashboard_response())
