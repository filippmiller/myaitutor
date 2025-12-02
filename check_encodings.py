
import os
from dotenv import load_dotenv
import grpc
from yandex.cloud.ai.stt.v2 import stt_service_pb2

print(dir(stt_service_pb2.RecognitionConfig))
