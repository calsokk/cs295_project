# Doc: Natural_Language_Code/build/info_build.md
# Luau Compiler Fuzzing Environment (x86_64)

FROM ubuntu:latest

# Install build tools and dependencies
RUN apt-get update && apt-get install -y \
    llvm clang lld \
    cmake make \
    git \
    python3 python3-pip python3-venv \
    vim \
    xxd \
    && rm -rf /var/lib/apt/lists/*

# Install Python fuzzing dependencies
RUN pip3 install "atheris==2.3.0" --break-system-packages 2>/dev/null || pip3 install "atheris==2.3.0"

# Set up working directory
RUN mkdir -p /home/student
WORKDIR /home/student

# Clone Luau and pin to a specific version for reproducibility
RUN git clone https://github.com/luau-lang/luau.git luau
WORKDIR /home/student/luau
RUN git checkout 0.712

# Build fuzz targets using the Makefile with ASan + libFuzzer
# config=fuzz adds: -fsanitize=address,fuzzer -O2
RUN make -j$(nproc) config=fuzz fuzz-parser fuzz-compiler fuzz-typeck fuzz-linter

# Also build luau-compile for grammar fuzzer validation
RUN make -j$(nproc) luau-compile

# Go back to student dir
WORKDIR /home/student

# Copy project files
COPY grammar_fuzzer grammar_fuzzer
COPY seed_corpus seed_corpus
COPY scripts scripts

# Create output directories
RUN mkdir -p shared/corpus shared/crashes shared/logs
