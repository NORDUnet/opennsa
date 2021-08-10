# OpenNSA docker image

FROM debian:stable-slim

MAINTAINER Henrik Thostrup Jensen <htj@nordu.net>


# -- Environment --
ENV GIT_REPO https://github.com/NORDUnet/opennsa
ENV USER opennsa


# -- User setup --
RUN adduser --disabled-password --gecos 'OpenNSA user' $USER


# --- Base image ---
# Update and install dependencies
# pip to install twistar service-identity pyasn1
# pyasn1 and crypto is needed for ssh backends
RUN apt update \
 && apt install -y \
    git-core \
    python3 \
    python3-twisted-bin \
    python3-openssl \
    python3-psycopg2 \
    python3-pip \
    python3-crypto \
    python3-dateutil \
 && pip3 install \
    twistar \
    service-identity \
    pyasn1 \
# -- Instal OpenNSA --
 && echo git clone $GIT_REPO \
 && su - $USER -c "git clone $GIT_REPO" \
# -- Cleanup --
 && apt remove -y \
    git-core \
    python3-pip \
 && apt autoremove -y \
 && rm -rf /var/lib/apt/lists/*


# -- Switch to OpenNSA directory --
USER $USER
WORKDIR /home/$USER/opennsa

ENV PYTHONPATH .


# -- Entrypoint --

EXPOSE 9080
EXPOSE 9443

ENTRYPOINT rm -f twistd.pid; twistd -ny opennsa.tac

