# Basing on the Debian 13 (trixie) used on the Proxmox LXC
FROM debian:trixie-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-nacl python3-cryptography python3-cbor2 \
      python3-pytest sqlite3 \
 && rm -rf /var/lib/apt/lists/*

COPY acme  /opt/acme/acme
COPY bin   /opt/acme/bin
COPY tests /opt/acme/tests
RUN chmod 755 /opt/acme/bin/* && mkdir -p /srv

WORKDIR /opt/acme
ENV PYTHONDONTWRITEBYTECODE=1

# The containers idle; all work is done with `docker exec`.
CMD ["sleep", "infinity"]