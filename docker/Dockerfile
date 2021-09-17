# OpenNSA docker image

FROM debian:stable-slim

LABEL maintainer="Henrik Thostrup Jensen <htj@nordu.net>"

# -- Environment --
ENV GIT_REPO https://github.com/NORDUnet/opennsa
ENV USER opennsa


# -- User setup --
RUN adduser --disabled-password --gecos 'OpenNSA user' $USER
ADD . /home/$USER/opennsa/

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
   python3-cryptography \
   python3-dateutil \
   && pip3 install \
   twistar \
   service-identity \
   pyasn1 \
   # -- Instal OpenNSA --
   # && echo git clone $GIT_REPO \
   # && su - $USER -c "git clone $GIT_REPO" \
   ## Unsure why but this needs to be pulled away from the main apt install
   && chown $USER:$USER -R /home/opennsa/opennsa \
   && apt install -y netcat iputils-ping \
   # -- Cleanup --
   && apt remove -y git-core python3-pip  \
   && apt autoremove -y \
   && rm -rf /var/lib/apt/lists/* \
   && cp /home/$USER/opennsa/docker/run_opennsa.sh /home/$USER/opennsa \
   && cp /home/$USER/opennsa/config/opennsa.conf.template  /home/$USER/opennsa/config/opennsa.conf


#RUN 
# -- Switch to OpenNSA directory --
USER $USER

WORKDIR /home/$USER/opennsa

ENV PYTHONPATH .
# -- Entrypoint --
EXPOSE 9080
EXPOSE 9443

# USER root

CMD /home/$USER/opennsa/run_opennsa.sh
