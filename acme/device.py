# Name: device.py
# Nodes: Server, console. & cartridge (/opt/acme/acme/)
# Purpose: The device side's provisioning too
# Notes:
#   - init will generate kesy locally and write the signing request
#   - install will add certs (in the cartridge case, a whole image built)
#   - status will verify the image
# ===================================================================
# Libraries:
import os, sys, argparse
from pathlib import Path
from . import keystore as K
from .cert import CertError, Role
from .issuer import _print, describe