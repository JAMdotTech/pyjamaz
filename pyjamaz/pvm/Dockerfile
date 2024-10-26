FROM ubuntu:latest

# Note:
# Ik kreeg lpython niet lokaal gecompileerd, waarschijnlijk door OS dependecies, met deze docker file trek ik een custom
# build op waarmee we kunnen compilen naar WASM

# Set non-interactive frontend and timezone
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Minsk
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Update and install necessary packages
RUN apt -y update && apt -y upgrade
RUN apt -y install git build-essential binutils-dev clang zlib1g-dev cmake curl bison re2c

# Install Emscripten from Git
RUN mkdir $HOME/ext && cd $HOME/ext \
    && git clone https://github.com/emscripten-core/emsdk.git \
    && cd emsdk \
    && ./emsdk install latest \
    && ./emsdk activate latest \
    && ./emsdk install node-18.20.3-64bit \
    && ./emsdk activate node-18.20.3-64bit

RUN set -ex
SHELL ["/bin/bash", "-c"]

# Set up Emscripten and Node environment
RUN echo 'source $HOME/ext/emsdk/emsdk_env.sh' >> ~/.bashrc

# Verify installation of Emscripten and Node
RUN source $HOME/ext/emsdk/emsdk_env.sh \
    && emcc -v \
    && em++ -v \
    && which node \
    && node -v

###################################################### \

#https://github.com/conda-forge/miniforge-images/blob/master/ubuntu/Dockerfile
ARG MINIFORGE_NAME=Miniforge3
ARG MINIFORGE_VERSION=24.7.1-2
ARG TARGETPLATFORM

ENV CONDA_DIR=/opt/conda
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PATH=${CONDA_DIR}/bin:${PATH}

RUN apt-get update > /dev/null && \
    apt-get install --no-install-recommends --yes \
        wget bzip2 ca-certificates \
        git \
        tini \
        > /dev/null && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    wget --no-hsts --quiet https://github.com/conda-forge/miniforge/releases/download/${MINIFORGE_VERSION}/${MINIFORGE_NAME}-${MINIFORGE_VERSION}-Linux-$(uname -m).sh -O /tmp/miniforge.sh && \
    /bin/bash /tmp/miniforge.sh -b -p ${CONDA_DIR} && \
    rm /tmp/miniforge.sh && \
    conda clean --tarballs --index-cache --packages --yes && \
    find ${CONDA_DIR} -follow -type f -name '*.a' -delete && \
    find ${CONDA_DIR} -follow -type f -name '*.pyc' -delete && \
    conda clean --force-pkgs-dirs --all --yes  && \
    echo ". ${CONDA_DIR}/etc/profile.d/conda.sh && conda activate base" >> /etc/skel/.bashrc && \
    echo ". ${CONDA_DIR}/etc/profile.d/conda.sh && conda activate base" >> ~/.bashrc

###################################################### \

RUN git clone https://github.com/lcompilers/lpython.git
WORKDIR ./lpython

SHELL ["/bin/bash", "-c"]

RUN echo $'name: lp\n\
channels:\n\
  - conda-forge\n\
dependencies:\n\
  - git\n\
  - pip\n\
  - make\n\
  - re2c\n\
  - toml\n\
  - zlib\n\
  - cmake\n\
  - numpy=1.26.4\n\
  - flake8\n\
  - setuptools\n\
  - bison=3.4\n\
  - python=3.10.2\n\
  - llvmdev=11.0.1\n\
  - zstd\n\
  - zstd-static'\
>> env.yml

#RUN conda env create -f environment_unix.yml
RUN conda env create -f env.yml

# Make RUN commands use the new environment:
SHELL ["conda", "run", "-n", "lp", "/bin/bash", "-c"]

# install lpython (older, missing some functionality)
#RUN conda init && conda activate lp
#RUN conda install lpython -c conda-forge

# Uncomment if you want to build from sources (latest)
RUN ./build0.sh
RUN ./build1.sh

# Compile lpython.wasm
#RUN source $HOME/ext/emsdk/emsdk_env.sh \
#    && ./build_to_wasm.sh
