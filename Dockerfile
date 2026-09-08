ARG PYTHON_BASE_IMAGE_DIGEST_REF
FROM ${PYTHON_BASE_IMAGE_DIGEST_REF}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libltdl7 \
        libkrb5-3 \
        libgssapi-krb5-2 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements-runtime.txt /app/requirements-runtime.txt

RUN python -m pip install --no-cache-dir -r /app/requirements-runtime.txt

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin appuser

COPY src /app/src

USER appuser

EXPOSE 3978

CMD ["python", "-m", "src.production_main"]