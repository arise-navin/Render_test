#!/usr/bin/env python3
"""
ServiceNow AI Copilot Setup Script
This script helps configure the application for first-time use.
"""

import os
import sys

def print_banner():
    print("=" * 70)
    print("  ServiceNow AI Copilot - Setup Wizard")
    print("=" * 70)
    print()

def check_python_version():
    print("Checking Python version...")
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def check_dependencies():
    print("\nChecking dependencies...")
    required_packages = [
        'fastapi',
        'uvicorn',
        'requests',
        'psycopg2',
        'reportlab'
    ]
    
    missing = []
    for package in required_packages:
        try:
            if package == 'psycopg2':
                __import__('psycopg2')
            else:
                __import__(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} - NOT INSTALLED")
            missing.append(package)
    
    if missing:
        print("\n❌ Missing packages detected")
        print("   Run: pip install -r requirements.txt")
        return False
    
    print("✓ All dependencies installed")
    return True

def check_directory_structure():
    print("\nChecking directory structure...")
    required_dirs = [
        'agents',
        'services',
        'static/css',
        'static/js',
        'templates'
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"✓ {dir_path}")
        else:
            print(f"✗ {dir_path} - MISSING")
            all_exist = False
    
    if not all_exist:
        print("\n❌ Directory structure incomplete")
        return False
    
    print("✓ Directory structure OK")
    return True

def check_configuration():
    print("\nChecking configuration files...")
    
    # Check MySQL configuration
    try:
        db_url = os.environ.get('DATABASE_URL', '')
        if db_url:
            print(f"✓ DATABASE_URL found")
            print(f"  - URL: {db_url[:40]}...")
        else:
            print("✗ DATABASE_URL not set — add it to environment variables")
    except Exception as e:
        print(f"✗ Postgres config error: {e}")
        return False
    
    # Check ServiceNow configuration
    try:
        from services.servicenow_client import SN_INSTANCE, SN_USER, SN_PASS
        print(f"✓ ServiceNow config found")
        print(f"  - Instance: {SN_INSTANCE}")
        print(f"  - User: {SN_USER}")
        
        if 'dev229640' in SN_INSTANCE:
            print("  ⚠️  Warning: Using demo instance URL")
    except Exception as e:
        print(f"✗ ServiceNow config error: {e}")
        return False
    
    # Check Ollama configuration
    try:
        from ollama_client import OLLAMA_URL, MODEL
        print(f"✓ Ollama config found")
        print(f"  - URL: {OLLAMA_URL}")
        print(f"  - Model: {MODEL}")
    except Exception as e:
        print(f"✗ Ollama config error: {e}")
        return False
    
    return True

def test_postgres_connection():
    print("\nTesting Postgres connection...")
    try:
        from services.database import get_conn
        conn = get_conn()
        conn.close()
        print("✓ Postgres connection successful")
        return True
    except Exception as e:
        print(f"✗ Postgres connection failed: {e}")
        print("  Please ensure DATABASE_URL is set correctly")
        return False

def test_ollama_connection():
    print("\nTesting Ollama connection...")
    try:
        import requests
        from ollama_client import OLLAMA_URL
        response = requests.get(OLLAMA_URL.replace('/api/generate', '/api/tags'), timeout=5)
        if response.status_code == 200:
            print("✓ Ollama connection successful")
            models = response.json().get('models', [])
            print(f"  Available models: {len(models)}")
            return True
        else:
            print(f"✗ Ollama returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Ollama connection failed: {e}")
        print("  Please ensure Ollama is running on http://localhost:11434")
        return False

def show_next_steps():
    print("\n" + "=" * 70)
    print("  Next Steps")
    print("=" * 70)
    print()
    print("1. Configure your ServiceNow credentials in services/servicenow_client.py")
    print("2. Set DATABASE_URL in Render → Environment variables")
    print("3. Ensure Ollama is running with the correct model")
    print("4. Start the application:")
    print()
    print("   python -m uvicorn main:app --reload")
    print()
    print("5. Open your browser to: http://127.0.0.1:8000/")
    print()
    print("=" * 70)

def main():
    print_banner()
    
    checks_passed = []
    
    # Run checks
    checks_passed.append(("Python Version", check_python_version()))
    checks_passed.append(("Directory Structure", check_directory_structure()))
    checks_passed.append(("Dependencies", check_dependencies()))
    checks_passed.append(("Configuration", check_configuration()))
    checks_passed.append(("Postgres Connection", test_postgres_connection()))
    checks_passed.append(("Ollama Connection", test_ollama_connection()))
    
    # Summary
    print("\n" + "=" * 70)
    print("  Setup Summary")
    print("=" * 70)
    
    for check_name, passed in checks_passed:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{check_name:.<40} {status}")
    
    total_checks = len(checks_passed)
    passed_checks = sum(1 for _, passed in checks_passed if passed)
    
    print()
    print(f"Results: {passed_checks}/{total_checks} checks passed")
    
    if passed_checks == total_checks:
        print("\n🎉 Setup complete! Your application is ready to run.")
        show_next_steps()
        return 0
    else:
        print("\n⚠️  Some checks failed. Please review the errors above.")
        show_next_steps()
        return 1

if __name__ == "__main__":
    sys.exit(main())


