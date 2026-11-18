FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git socat libicu72 libssl3 libkrb5-3 liblttng-ust1 zlib1g libatomic1 && rm -rf /var/lib/apt/lists/*
WORKDIR /runner
# Official actions/runner v2.338.2 release assets; checksums from GitHub release metadata.
RUN case "$(dpkg --print-architecture)" in \
      arm64) platform=arm64; checksum=670adb2f268fe21dcbb58b3db0e0aa9d5b3bddfe2c651481336e561ff86de945 ;; \
      amd64) platform=x64; checksum=baebf204307bac6193480852732f0aba2ae97b6c5597c244f4d5558390147c40 ;; \
      *) exit 1 ;; esac && \
    curl --fail --location --retry 2 --max-time 240 "https://github.com/actions/runner/releases/download/v2.338.2/actions-runner-linux-${platform}-2.338.2.tar.gz" -o /tmp/runner.tar.gz && \
    printf '%s  /tmp/runner.tar.gz\n' "$checksum" | sha256sum -c - && tar xzf /tmp/runner.tar.gz && rm /tmp/runner.tar.gz && \
    useradd --create-home --uid 1001 runner && chown -R runner:runner /runner
COPY entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh
USER runner
ENV PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["/entrypoint.sh"]
