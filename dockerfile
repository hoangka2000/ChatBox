FROM python:3.10

WORKDIR /app


RUN pip install --upgrade pip && \
    pip install lmstudio flask transformers timm optimum accelerate

COPY . .

CMD ["python", "Test.py"]