# OpenNSA docker image

FROM debian:stable-slim

MAINTAINER Henrik Thostrup Jensen <htj@nordu.net>


# -- Environment --
ENV GIT_REPO git://git.nordu.net/opennsa.git
ENV USER opennsa


# --- Base image ---
# Update and install dependencies
# pip to install twistar
# pyasn1 and crypto is needed for ssh backends
RUN apt-get update && apt-get install -y git-core python python-twisted python-openssl python-psycopg2 python-pip python-pyasn1 python-crypto

RUN pip install twistar


# -- User setup --
RUN adduser --disabled-password --gecos 'OpenNSA user' $USER


# -- Install OpenNSA --
USER $USER
WORKDIR /home/$USER

RUN echo git clone $GIT_REPO
RUN git clone $GIT_REPO

# -- Cleanup --
# With --squash this makes the image go from 476 to 164 mb
USER root
RUN apt-get remove -y python-pip git
RUN apt-get -y clean
RUN apt-get -y autoclean
RUN apt-get -y autoremove


# -- Switch to OpenNSA directory --

USER $USER
WORKDIR /home/$USER/opennsa

ENV PYTHONPATH .


# -- Entrypoint --

EXPOSE 9080
EXPOSE 9443

ENTRYPOINT rm -f twistd.pid; twistd -ny opennsa.tac

