FROM ubuntu:16.04

ARG BASE_DIR=/root/featmaker
ARG SOURCE_DIR=/root/featmaker/
ARG SANDBOX_DIR=/tmp

EXPOSE 2023

RUN apt-get -y update 
RUN apt-get install build-essential curl libcap-dev git cmake libcursesw5 libncurses5 libncurses5-dev python3-minimal python3-pip unzip libtcmalloc-minimal4 libgoogle-perftools-dev libsqlite3-dev doxygen python3 python3-pip
RUN pip3 install tabulate numpy scikit-learn
RUN apt-get install clang-6.0 llvm-6.0 llvm-6.0-dev llvm-6.0-tools
RUN ln -s /usr/bin/clang-6.0 /usr/bin/clang
RUN ln -s /usr/bin/clang++-6.0 /usr/bin/clang++
RUN ln -s /usr/bin/llvm-config-6.0 /usr/bin/llvm-config
RUN ln -s /usr/bin/llvm-link-6.0 /usr/bin/llvm-link

# Clone git dir
WORKDIR /root
RUN git clone https://github.com/annonymousfeatmaker/featmaker.git

# Install stp solver
RUN apt-get install cmake bison flex libboost-all-dev python perl zlib1g-dev minisat
WORKDIR ${BASE_DIR}
RUN git clone https://github.com/stp/stp.git
WORKDIR ${BASE_DIR}/stp
RUN git checkout tags/2.3.3
RUN mkdir build
WORKDIR ${BASE_DIR}/stp/build
RUN cmake ..
RUN make
RUN make install

RUN echo "ulimit -s unlimited" >> /root/.bashrc

# install klee-uclibc
WORKDIR ${BASE_DIR}
RUN git clone https://github.com/klee/klee-uclibc.git
WORKDIR ${BASE_DIR}/klee-uclibc
RUN chmod 777 -R *
RUN ./configure --make-llvm-lib
RUN make -j2

# install klee
WORKDIR ${BASE_DIR}/klee
RUN echo "export LLVM_COMPILER=clang" >> /root/.bashrc
RUN echo "KLEE_REPLAY_TIMEOUT=1" >> /root/.bashrc
RUN mkdir build
WORKDIR ${BASE_DIR}/klee/build
RUN cmake -DENABLE_SOLVER_STP=ON -DENABLE_POSIX_RUNTIME=ON -DENABLE_UNIT_TESTS=OFF -DENABLE_SYSTEM_TESTS=OFF -DENABLE_KLEE_UCLIBC=ON -DKLEE_UCLIBC_PATH=${BASE_DIR}/klee-uclibc -DLLVM_CONFIG_BINARY=/usr/bin/llvm-config -DLLVMCC=/usr/bin/clang ..
RUN make
WORKDIR ${BASE_DIR}/klee
RUN env -i /bin/bash -c '(source testing-env.sh; env > test.env)'

WORKDIR ${BASE_DIR}
