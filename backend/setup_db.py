#!/usr/bin/env python
"""
PostgreSQL Setup Helper
Creates the user and database needed for the application
"""
import subprocess
import sys

def run_sql(sql, user='postgres', database='postgres'):
    """Run SQL command using psql"""
    try:
        result = subprocess.run(
            ['psql', '-U', user, '-d', database, '-c', sql],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, '', str(e)

print("=" * 60)
print("PostgreSQL Setup Helper")
print("=" * 60)

# Create user
print("\n1. Creating user 'sanju'...")
success, stdout, stderr = run_sql(
    "CREATE USER sanju WITH PASSWORD 'sanju140908';"
)
if success or 'already exists' in stderr:
    print("   ✓ User created or already exists")
else:
    print(f"   ✗ Failed: {stderr}")
    sys.exit(1)

# Create database
print("\n2. Creating database 'testdb'...")
success, stdout, stderr = run_sql(
    "CREATE DATABASE testdb OWNER sanju;",
    user='postgres'
)
if success or 'already exists' in stderr:
    print("   ✓ Database created or already exists")
else:
    print(f"   ✗ Failed: {stderr}")
    sys.exit(1)

# Grant privileges
print("\n3. Granting privileges...")
success, stdout, stderr = run_sql(
    "GRANT ALL PRIVILEGES ON DATABASE testdb TO sanju;",
    user='postgres'
)
if success:
    print("   ✓ Privileges granted")
else:
    print(f"   ✗ Failed: {stderr}")

print("\n" + "=" * 60)
print("Setup complete! You can now connect with:")
print("  User: sanju")
print("  Password: sanju140908")
print("  Database: testdb")
print("=" * 60)
