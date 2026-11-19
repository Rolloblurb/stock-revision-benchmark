FROM python:3.12-slim
WORKDIR /workspace
COPY . /workspace
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
