FROM public.ecr.aws/lambda/python:3.11

# Copy requirements.txt
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install the specified packages
RUN python3 -m pip install --upgrade pip
RUN yum install -y Cython libxml2-devel libxslt-devel
RUN yum -y groups mark install "Development Tools" && yum -y groups mark convert "Development Tools" && yum -y group install "Development Tools"
RUN pip install -r requirements.txt

# Additonal commands that may need to be run:
# RUN yum install -y poppler-utils
# RUN pip install yfinance

# Copy all files in ./src
COPY src/* ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler.
CMD [ "main.handler" ]