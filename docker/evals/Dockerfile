FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        afl++ \
        build-essential \
        ca-certificates \
        clang \
        curl \
        git \
        libprotobuf-dev \
        libprotobuf-mutator-dev \
        protobuf-compiler \
        python3 \
        python3-pip \
        python3-venv \
        rustc \
        cargo \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY pyproject.toml uv.lock ./
COPY guardian ./guardian
RUN python3 -m venv /opt/guardian-venv \
    && /opt/guardian-venv/bin/pip install --upgrade pip \
    && /opt/guardian-venv/bin/pip install -e .

ENV PATH="/opt/guardian-venv/bin:${PATH}"

COPY scripts/build_and_fuzz_case.sh /opt/guardian-evals/build_and_fuzz_case.sh
RUN chmod +x /opt/guardian-evals/build_and_fuzz_case.sh

CMD ["python", "-m", "guardian.evals", "--help"]
