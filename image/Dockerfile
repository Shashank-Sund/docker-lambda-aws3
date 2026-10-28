# Python 3.13 base runs on Amazon Linux 2023, so current numpy/pandas wheels
# install directly (the 3.11 base is Amazon Linux 2, which forced source builds).
FROM public.ecr.aws/lambda/python:3.13 AS runtime

# Lambda's filesystem is read-only except /tmp. Without this, matplotlib warns and
# creates a new temporary config directory on every cold start.
ENV MPLCONFIGDIR=/tmp/matplotlib

# Copy requirements.txt
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install the pinned packages
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Copy all files in ./src
COPY src/* ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler.
CMD [ "main.handler" ]

# Test image: same OS and packages as the Lambda, plus pytest.
# Build with: docker build --target test -t stock-eda:test image
FROM runtime AS test
COPY requirements-dev.txt ${LAMBDA_TASK_ROOT}
RUN python3 -m pip install --no-cache-dir -r requirements-dev.txt
COPY tests/ ${LAMBDA_TASK_ROOT}/tests/
ENTRYPOINT [ "python3", "-m", "pytest", "-q", "tests" ]
CMD [ "-m", "not live" ]

# Default build target is the Lambda image.
FROM runtime
