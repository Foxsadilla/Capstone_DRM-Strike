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