FROM nuvladev/job-docker-compose-client:master

ARG workdir="/opt/nuvlabox"

WORKDIR ${workdir}

COPY . .

ENV PATH="$PATH:${workdir}/common:${workdir}/commands" \
    WORKDIR="${workdir}"

ENTRYPOINT ["./installer"]