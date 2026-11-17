# Minimal TCP forwarder that lets the host reach lab services that live on
# the internal-only lab-net. It forwards to ONE fixed upstream (given as
# socat arguments in docker-compose.yml) and runs unprivileged.
FROM alpine:3.20
RUN apk add --no-cache socat
USER nobody
ENTRYPOINT ["socat"]
