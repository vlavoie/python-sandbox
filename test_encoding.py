"""
Test script to verify UTF-8 encoding is working correctly on Windows.
Run this before launching the main app to diagnose encoding issues.
"""

import sys
import locale
import os

print("=" * 60)
print("UTF-8 Encoding Test")
print("=" * 60)

# Test 1: Platform
print(f"\n1. Platform: {sys.platform}")
print(f"   Python version: {sys.version}")

# Test 2: Current encoding
print(f"\n2. Current encodings:")
print(f"   stdout encoding: {sys.stdout.encoding}")
print(f"   stderr encoding: {sys.stderr.encoding}")
print(f"   filesystem encoding: {sys.getfilesystemencoding()}")
print(f"   default encoding: {sys.getdefaultencoding()}")
print(f"   locale encoding: {locale.getpreferredencoding()}")

# Test 3: Environment variables
print(f"\n3. Environment variables:")
print(f"   PYTHONUTF8: {os.environ.get('PYTHONUTF8', 'not set')}")
print(f"   PYTHONIOENCODING: {os.environ.get('PYTHONIOENCODING', 'not set')}")

# Test 4: Try to print emojis
print(f"\n4. Emoji test:")
try:
    print("   🚀 Rocket emoji")
    print("   ✅ Check mark emoji")
    print("   ❌ Cross mark emoji")
    print("   ✓ All emojis printed successfully!")
except Exception as e:
    print(f"   ✗ Error printing emojis: {e}")

# Test 5: Try to open and read the skill files
print(f"\n5. Skill file test:")
from pathlib import Path
skill_dir = Path(__file__).parent

files_to_test = [
    "fpv-pov-image.md",
    "fpv-pov-review.md"
]

for filename in files_to_test:
    filepath = skill_dir / filename
    if filepath.exists():
        try:
            with open(filepath, "r", encoding='utf-8', errors='replace') as f:
                content = f.read(100)  # Read first 100 chars
            print(f"   ✓ {filename} - OK (read {len(content)} chars)")
        except Exception as e:
            print(f"   ✗ {filename} - ERROR: {e}")
    else:
        print(f"   ✗ {filename} - FILE NOT FOUND")

# Test 6: Reconfigure test
print(f"\n6. Testing stdout reconfiguration:")
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
        print(f"   ✓ Reconfigured to UTF-8")
        print(f"   stdout encoding after: {sys.stdout.encoding}")
    except Exception as e:
        print(f"   ✗ Reconfiguration failed: {e}")
else:
    print(f"   ! reconfigure() not available (Python < 3.7)")
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        print(f"   ✓ Wrapped stdout/stderr with UTF-8")
    except Exception as e:
        print(f"   ✗ Wrapping failed: {e}")

print("\n" + "=" * 60)
print("If all tests pass, the app should work correctly.")
print("If emoji test fails, UTF-8 encoding is not working properly.")
print("=" * 60)
