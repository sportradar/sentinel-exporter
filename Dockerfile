FROM python:2
EXPOSE 9478/tcp
WORKDIR /app
CMD python sentinel_exporter.py
COPY requirements.txt /app/requirements.txt
ADD *.py /app/
RUN pip install -r /app/requirements.txt
