FROM nuvladev/job-docker-compose-client:master

ARG workdir="/opt/nuvlabox"

RUN apk add --no-cache curl

WORKDIR ${workdir}

COPY . .

ENV PATH="$PATH:${workdir}/common:${workdir}/commands" \
    WORKDIR="${workdir}" \
    ROOTFS="/rootfs"

ENTRYPOINT ["./installer"]