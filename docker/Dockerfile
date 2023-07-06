# OpenNSA docker image

FROM debian:stable-slim

LABEL maintainer="Henrik Thostrup Jensen <htj@nordu.net>"

# -- Environment --
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
   libpq-dev \
   python3 \
   python3-pip \
   netcat-openbsd \
   iputils-ping && \
   pip3 install --break-system-packages -r /home/$USER/opennsa/requirements.txt  && \
   chown $USER:$USER -R /home/opennsa/opennsa \
   # -- Cleanup --
   && apt remove -y python3-pip  \
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
