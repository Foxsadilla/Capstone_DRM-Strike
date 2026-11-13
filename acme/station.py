# Name: station.py
# Nodes: ALL (/opt/acme/acme/)
# Purpose: Manufactures and provisions the incoming sign requests and outputs the certificates
# Notes:
#   - Consists of the following:
#       - trust             - load Cert_ACME and the update certificates
#       - accept            - take a signing request from a console or server
#       - new-cartridge     - generate a cartridge's keys and request here
#       - export-requests   - hand pending requests to the offline issuer
#       - receive           -  check returned certificates against the requests
#       - export            - hand a device its certificates (console/server) or its complete image (cartridge)
#       - erase             - destroy the station's copy of a cartridge's keys
# ===================================================================