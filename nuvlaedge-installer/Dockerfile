ARG ALPINE_MAJ_MIN_VERSION="3.18"
ARG PYTHON_MAJ_MIN_VERSION="3.11"

ARG BASE_IMAGE=python:${PYTHON_MAJ_MIN_VERSION}-alpine${ALPINE_MAJ_MIN_VERSION}

FROM ${BASE_IMAGE}

ARG workdir="/opt/nuvlaedge"

WORKDIR ${workdir}

COPY . .
COPY target/ .

RUN apk add --no-cache jq docker-cli docker-cli-compose
RUN pip install --no-cache-dir docker

ENV PATH="$PATH:${workdir}/common:${workdir}/commands" \
    WORKDIR="${workdir}" \
    ROOTFS="/rootfs"  \
    ROOTFS_WORKING_DIR="/rootfs-working-dir"

RUN chmod +x installer

ENTRYPOINT ["./installer"]
