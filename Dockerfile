FROM ubuntu:bionic

# System dependencies
RUN apt-get update && apt-get install --yes python3-pip

# Python dependencies
ENV LANG C.UTF-8
RUN pip3 install --upgrade pip

# Set git commit ID
ARG COMMIT_ID
ENV COMMIT_ID=$COMMIT_ID
RUN test -n "${COMMIT_ID}"

# Import code, install code dependencies
WORKDIR /srv
ADD . .
RUN pip3 install -r requirements.txt

# Setup commands to run server
ENTRYPOINT ["talisker.gunicorn", "app:app", "--access-logfile", "-", "--error-logfile", "-", "--bind"]
CMD ["0.0.0.0:80"]
