# Name: issuer.py
# Nodes: host (i.e., pve4) (/opt/acme/acme/)
# Purpose: Functions as the issuer for ACME psuedo offline factory
# Notes:
#   - State directory:
#       - root/root.key issuing key
#       - root/root.cert Cert_ACME
#       - update/primary.*   update-signing key + cert (role update)
#       - update/backup.* backup update key + cert  (role update)
#       - issued.jsonl  one line per certificate ever issued
# ===================================================================
# Libraries:

import argparse, hashlib, json, os, sys, time
from pathlib import Path

from . import cert as C
from . import crypto
from . import csr as R
from .cert import CertError, Role

DAY = 86400
DEFAULT_HOME = "/var/lib/acme-issuer"

class IssueError(Exception):
    pass

# ===================================================================
# Emulated Air-gapped environment:

# ===================================================================
# Storage:

# ===================================================================
# Log of Issuing:

# ===================================================================
# Root Certificate gen


# ===================================================================
# Updating keys

# ===================================================================
# Issuance of Cert


# ===================================================================
# Description Display

# ===================================================================
# Simulated CLI of System