import sys
from unittest.mock import MagicMock

# MOCK HEAVY ML MODELS BEFORE IMPORTING APP
# This prevents the 30-second CPU load of bge-m3 and bge-reranker-base during test collection
sys.modules['langchain_huggingface'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()
