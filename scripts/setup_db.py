#!/usr/bin/env python3
"""
Setup PostgreSQL databases for Fog Compute
Creates the production and test databases with proper user permissions
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys

def setup_databases():
    """Create databases and user for fog compute"""

    # Connect to PostgreSQL server
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",  # Default postgres password
            dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        print("✓ Connected to PostgreSQL server")

        # Create user if not exists
        try:
            cursor.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'fog_user') THEN
                        CREATE USER fog_user WITH PASSWORD 'fog_password';
                    END IF;
                END
                $$;
            """)
            print("✓ Created user: fog_user")
        except Exception as e:
            print(f"Note: User may already exist: {e}")

        # Create production database
        try:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'fog_compute'")
            if not cursor.fetchone():
                cursor.execute("CREATE DATABASE fog_compute OWNER fog_user")
                print("✓ Created database: fog_compute")
            else:
                print("✓ Database fog_compute already exists")
        except Exception as e:
            print(f"Note: Production database issue: {e}")

        # Create test database
        try:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'fog_compute_test'")
            if not cursor.fetchone():
                cursor.execute("CREATE DATABASE fog_compute_test OWNER fog_user")
                print("✓ Created database: fog_compute_test")
            else:
                print("✓ Database fog_compute_test already exists")
        except Exception as e:
            print(f"Note: Test database issue: {e}")

        # Grant permissions
        try:
            cursor.execute("GRANT ALL PRIVILEGES ON DATABASE fog_compute TO fog_user")
            cursor.execute("GRANT ALL PRIVILEGES ON DATABASE fog_compute_test TO fog_user")
            print("✓ Granted permissions to fog_user")
        except Exception as e:
            print(f"Note: Permission grant issue: {e}")

        cursor.close()
        conn.close()

        print("\n✅ Database setup complete!")
        print("\nDatabases created:")
        print("  - fog_compute (production)")
        print("  - fog_compute_test (testing)")
        print("\nUser: fog_user")
        print("Password: fog_password")

        return True

    except psycopg2.OperationalError as e:
        print(f"\n❌ Could not connect to PostgreSQL server")
        print(f"Error: {e}")
        print("\nPlease check:")
        print("  1. PostgreSQL is running")
        print("  2. Default postgres user password is 'postgres'")
        print("  3. Port 5432 is accessible")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = setup_databases()
    sys.exit(0 if success else 1)
