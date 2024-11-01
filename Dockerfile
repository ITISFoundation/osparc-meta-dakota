FROM ubuntu:22.04 as base

RUN useradd -m -r osparcuser

USER root

ENV DEBIAN_FRONTEND noninteractive
ENV DEBCONF_NOWARNINGS="yes"

RUN apt-get update --yes && apt-get upgrade --yes 
RUN apt-get install -y --no-install-recommends apt-utils
RUN apt-get install --yes --no-install-recommends python3 python-is-python3 python3-venv wget python3-pip gosu

# Copying boot scripts                                                                                                                                                                                                                                                                                                   
COPY docker_scripts /docker

RUN pip3 install itis-dakota osparc_filecomms --upgrade

USER osparcuser

WORKDIR /home/osparcuser
RUN python3 -m venv venv
RUN . ./venv/bin/activate && pip3 install --upgrade -r /docker/requirements.txt

USER root
EXPOSE 8888

ENTRYPOINT [ "/bin/bash", "-c", "/docker/entrypoint.bash" ]
