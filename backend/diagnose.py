#!/usr/bin/env python
"""
Diagnostic script to check database connectivity
"""
import socket
import subprocess
import sys

def test_port_open(host, port):
    """Test if port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        return False

def test_psql():
    """Test with psql command"""
    try:
        result = subprocess.run(
            ['psql', '-U', 'sanju', '-h', 'localhost', '-p', '5432', '-d', 'testdb', '-c', 'SELECT 1'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return True, "psql connection successful"
        else:
            return False, f"psql error: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "psql timeout"
    except FileNotFoundError:
        return False, "psql not found in PATH"
    except Exception as e:
        return False, f"psql error: {e}"

print("=" * 60)
print("PostgreSQL Connection Diagnostic")
print("=" * 60)

# Test 1: Port connectivity
print("\n1. Testing port connectivity...")
if test_port_open('127.0.0.1', 5432):
    print("   ✓ Port 127.0.0.1:5432 is open")
else:
    print("   ✗ Port 127.0.0.1:5432 is NOT open")

if test_port_open('localhost', 5432):
    print("   ✓ Port localhost:5432 is open")
else:
    print("   ✗ Port localhost:5432 is NOT open")

# Test 2: psql connectivity
print("\n2. Testing psql connection...")
success, message = test_psql()
if success:
    print(f"   ✓ {message}")
else:
    print(f"   ✗ {message}")

print("\n" + "=" * 60)
if test_port_open('127.0.0.1', 5432) or test_port_open('localhost', 5432):
    print("PostgreSQL is reachable. Check user/password/database.")
else:
    print("PostgreSQL cannot be reached on any interface!")
    print("Check if PostgreSQL is running and configured for TCP connections.")
print("=" * 60)
