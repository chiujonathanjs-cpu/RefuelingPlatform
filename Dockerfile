FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libjpeg-dev zlib1g-dev libfreetype6-dev liblcms2-dev libwebp-dev \
    tcl-dev tk-dev python3-tk \
    libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt
RUN pip install opencv-python
RUN python -m pip install "paddleocr[all]"

COPY app.py .
EXPOSE 8000

CMD ["gunicorn", "--bind=0.0.0.0:8000", "app:app"]
