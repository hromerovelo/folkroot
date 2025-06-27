# BSD 2-Clause License
# 
# Copyright (c) 2025, Hilda Romero-Velo
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# 
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
# 
# """
#   Created by Hilda Romero-Velo on February 2025.
# """

# Base image set to Ubuntu 22.04 for stability and compatibility
FROM ubuntu:22.04

# Install essential packages, development tools, and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    build-essential \
    python3.11 \
    python3-pip \
    git \
    automake \
    libtool \
    autoconf \
    gawk \
    flex \
    bison \
    make \
    coreutils \
    zlib1g-dev \
    libcurl4-gnutls-dev \
    libsqlite3-dev \
    sqlite3 \
    inkscape \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Clone and build humdrum-tools
RUN git clone --recursive https://github.com/humdrum-tools/humdrum-tools.git /opt/humdrum-tools \
    && cd /opt/humdrum-tools/humdrum && make bin \
    && cd /opt/humdrum-tools/humextra && make library && make mid2hum && make extractx && make beat \
    && echo 'export PATH="$PATH:/opt/humdrum-tools/humdrum/bin:/opt/humdrum-tools/humextra/bin"' >> /etc/profile

# Clone and build humlib
RUN git clone https://github.com/craigsapp/humlib.git /opt/humlib \
    && cd /opt/humlib \
    && cp src/MuseRecord-notations.cpp src/MuseRecord-notations.cpp.orig \
    && sed '/\/\/ 92       \\/,/\/\/ 92       \\/d' src/MuseRecord-notations.cpp.orig \
    > src/MuseRecord-notations.cpp \
    && make library && make musicxml2hum && make mei2hum \
    && echo 'export PATH="$PATH:/opt/humlib/bin"' >> /etc/profile 

# Install Python packages.
RUN pip install matplotlib numpy==1.23 pandas openpyxl scikit-learn seaborn dendropy==5.0.1 verovio PyPDF2 plotly ete3 PyQt5 tqdm

# Create a non-root user and set up SSH service
RUN groupadd ssh \
    && useradd -m -s /bin/bash -G ssh user \
    && echo 'root:root' | chpasswd \
    && echo 'user:user' | chpasswd \
    && mkdir -p /run/sshd

# Copy 'folkroot' directory and set ownership to 'user:user', then apply 775 permissions
COPY --chown=user:user folkroot /home/user/folkroot
RUN chmod -R 775 /home/user/folkroot

# Expose port 22 for SSH access
EXPOSE 22

# Start SSH service
CMD ["/usr/sbin/sshd", "-D"]
