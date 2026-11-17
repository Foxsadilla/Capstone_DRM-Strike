# Name: test_cert.py
# Nodes: ALL (/tests/)
# Purpose: Testing the cert aspect of Phase 0
# Notes:
#   - Verify valid certs pass verfication (e.g., 16 byte serial num)
#   - Test that a cert is valid within its boundary timestamps
#   - Test that a cert will be rejected if it was signed by a forgien private key
#   - Test that a valid device cert cannot act as a CA to sign other device certs
#   - Test flipping a bit inside a cert payload to cause verification failure
#   - Test flipping a bit in the signature byte to cause a failure
#   - Test rejecting a cert is its embedded issuer serial num does not match the trusted root's
#   - Test that signtures are rejected if they were genereted without the SIG_CONTEXT
#   - Test that certs are rejected if their role does not match the one expected by server
#   - Test that the root cert will not be passed as a device cert
#   - Test expected roles by type error
#   -  
# ===================================================================