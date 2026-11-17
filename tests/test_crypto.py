# Name: test_crypto.py
# Nodes: ALL (/tests/)
# Purpose: Testing the crypto aspect of Phase 0
# Notes:
#   - Test sign and verify the round trip
#   - test the diffie hellman agreement
#   - Test tfor matching outputs when using HKDF with SHA-256 hash
#   -  Test Authenticated  Encryption with Associated Data tampering and roundtrip
# ===================================================================
# Libraries

import pytest
from acme import crypto

# ===================================================================
# Tests