# can be changed, however this offers a good compromise between recency and compatibility
FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

ENV QT_X11_NO_MITSHM=1

# Dependencies for OpenCV + GUI
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0t64 \
        libsm6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

RUN python -m venv /opt/.venv \
    && /opt/.venv/bin/pip install --upgrade pip \
    && /opt/.venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt


WORKDIR /opt
