"""
AI Task Handlers
FOG-006: Specialized handlers for AI workloads

Provides task handlers for common AI operations:
- Model inference
- Data preprocessing
- Model download/caching
"""
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Optional, Any

from task_engine.runner import TaskSpec, TaskResult, TaskStatus

logger = logging.getLogger(__name__)


class AITaskHandler(ABC):
    """
    Abstract base class for AI task handlers.

    FOG-006: Extensible AI task handling.
    """

    @property
    @abstractmethod
    def task_type(self) -> str:
        """Return the task type this handler handles."""
        pass

    @abstractmethod
    async def execute(self, spec: TaskSpec) -> TaskResult:
        """Execute the AI task."""
        pass

    def can_handle(self, spec: TaskSpec) -> bool:
        """Check if this handler can handle the task."""
        return spec.task_type == self.task_type


class AIInferenceHandler(AITaskHandler):
    """
    Handler for AI model inference tasks.

    FOG-006: Distributed inference across fog nodes.

    Supports:
    - Text generation/completion
    - Classification
    - Embedding generation
    - Custom model inference
    """

    @property
    def task_type(self) -> str:
        return "ai_inference"

    async def execute(self, spec: TaskSpec) -> TaskResult:
        """Execute AI inference task."""
        start_time = datetime.now(UTC)
        result = TaskResult(
            task_id=spec.task_id,
            status=TaskStatus.RUNNING,
            started_at=start_time,
        )

        payload = spec.payload
        inference_type = payload.get("type", "text_generation")
        model_id = payload.get("model_id", "default")

        try:
            if inference_type == "text_generation":
                result = await self._text_generation(result, payload)

            elif inference_type == "classification":
                result = await self._classification(result, payload)

            elif inference_type == "embedding":
                result = await self._embedding(result, payload)

            elif inference_type == "custom":
                result = await self._custom_inference(result, payload)

            else:
                result.status = TaskStatus.FAILED
                result.error_message = f"Unknown inference type: {inference_type}"
                return result

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = str(e)
            logger.error(f"AI inference task {spec.task_id} failed: {e}")

        result.completed_at = datetime.now(UTC)
        result.execution_time_ms = int(
            (result.completed_at - start_time).total_seconds() * 1000
        )

        return result

    async def _text_generation(
        self,
        result: TaskResult,
        payload: dict[str, Any]
    ) -> TaskResult:
        """Run text generation inference."""
        prompt = payload.get("prompt", "")
        max_tokens = payload.get("max_tokens", 100)
        temperature = payload.get("temperature", 0.7)
        model_id = payload.get("model_id", "default")

        # Simulate inference (in production, call actual model)
        await asyncio.sleep(0.1)  # Simulated latency

        # Placeholder response
        generated_text = f"[Generated response for: {prompt[:50]}...]"

        result.result_data = {
            "type": "text_generation",
            "model_id": model_id,
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": max_tokens,
            "generated_text": generated_text,
            "finish_reason": "length",
        }
        result.status = TaskStatus.COMPLETED

        return result

    async def _classification(
        self,
        result: TaskResult,
        payload: dict[str, Any]
    ) -> TaskResult:
        """Run classification inference."""
        text = payload.get("text", "")
        labels = payload.get("labels", ["positive", "negative", "neutral"])
        model_id = payload.get("model_id", "default")

        # Simulate inference
        await asyncio.sleep(0.05)

        # Placeholder scores
        import random
        scores = [random.random() for _ in labels]
        total = sum(scores)
        scores = [s / total for s in scores]

        predictions = [
            {"label": label, "score": score}
            for label, score in zip(labels, scores)
        ]
        predictions.sort(key=lambda x: x["score"], reverse=True)

        result.result_data = {
            "type": "classification",
            "model_id": model_id,
            "input_length": len(text),
            "predictions": predictions,
            "top_label": predictions[0]["label"],
            "top_score": predictions[0]["score"],
        }
        result.status = TaskStatus.COMPLETED

        return result

    async def _embedding(
        self,
        result: TaskResult,
        payload: dict[str, Any]
    ) -> TaskResult:
        """Generate text embeddings."""
        texts = payload.get("texts", [])
        if isinstance(texts, str):
            texts = [texts]

        model_id = payload.get("model_id", "default")
        dimensions = payload.get("dimensions", 384)

        # Simulate inference
        await asyncio.sleep(0.02 * len(texts))

        # Placeholder embeddings
        import random
        embeddings = [
            [random.gauss(0, 1) for _ in range(dimensions)]
            for _ in texts
        ]

        result.result_data = {
            "type": "embedding",
            "model_id": model_id,
            "num_texts": len(texts),
            "dimensions": dimensions,
            "embeddings": embeddings,
        }
        result.status = TaskStatus.COMPLETED

        return result

    async def _custom_inference(
        self,
        result: TaskResult,
        payload: dict[str, Any]
    ) -> TaskResult:
        """Run custom model inference."""
        model_id = payload.get("model_id", "custom")
        inputs = payload.get("inputs", {})

        # Simulate inference
        await asyncio.sleep(0.1)

        result.result_data = {
            "type": "custom",
            "model_id": model_id,
            "inputs_received": list(inputs.keys()),
            "outputs": {"status": "completed"},
        }
        result.status = TaskStatus.COMPLETED

        return result


class DataPreprocessHandler(AITaskHandler):
    """
    Handler for data preprocessing tasks.

    FOG-006: Distributed data preprocessing for AI pipelines.

    Supports:
    - Text cleaning/normalization
    - Tokenization
    - Feature extraction
    - Data transformation
    """

    @property
    def task_type(self) -> str:
        return "data_preprocess"

    async def execute(self, spec: TaskSpec) -> TaskResult:
        """Execute data preprocessing task."""
        start_time = datetime.now(UTC)
        result = TaskResult(
            task_id=spec.task_id,
            status=TaskStatus.RUNNING,
            started_at=start_time,
        )

        payload = spec.payload
        operation = payload.get("operation", "clean")

        try:
            if operation == "clean":
                result = await self._clean_text(result, payload)

            elif operation == "tokenize":
                result = await self._tokenize(result, payload)

            elif operation == "chunk":
                result = await self._chunk_text(result, payload)

            elif operation == "extract_features":
                result = await self._extract_features(result, payload)

            elif operation == "transform":
                result = await self._transform_data(result, payload)

            else:
                result.status = TaskStatus.FAILED
                result.error_message = f"Unknown preprocessing operation: {operation}"
                return result

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = str(e)
            logger.error(f"Data preprocessing task {spec.task_id} failed: {e}")

        result.completed_at = datetime.now(UTC)
        result.execution_time_ms = int(
            (result.completed_at - start_time).total_seconds() * 1000
        )

        return result

    async def _clean_text(
        self,
        result: TaskResult,
        payload: dict[str, Any]
    ) -> TaskResult:
        """Clean and normalize text data."""
        text = payload.get("text", "")
        lowercase = payload.get("lowercase", True)
        remove_html = payload.get("remove_html", True)
        remove_urls = payload.get("remove_urls", True)
        remove_special = payload.get("remove_special", False)

        cleaned = text

        # Basic cleaning operations
        if remove_html:
            import re
            cleaned = re.sub(r'<[^>]+>', '', cleaned)

        if remove_urls:
            import re
            cleaned = re.sub(r'https?://\S+', '', cleaned)

        if lowercase:
            cleaned = cleaned.lower()

        if remove_special:
            import re
            cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', cleaned)

        # Normalize whitespace
        cleaned = ' '.join(cleaned.split())

        result.result_data = {
            "operation": "clean",
            "original_length": len(text),
            "cleaned_length": len(cleaned),
            "cleaned_text": cleaned,
        }
        result.status = TaskStatus.COMPLETED

        return result

    async def _tokenize(
        self,
        result: TaskResult,
        payload: dict[str, Any]
    ) -> TaskResult:
        """Tokenize text into words or subwords."""
        text = payload.get("text", "")
        method = payload.get("method", "whitespace")  # whitespace, word, sentence

        if method == "whitespace":
            tokens = text.split()
        elif method == "word":
            import re
            tokens = re.findall(r'\b\w+\b', text.lower())
        elif method == "sentence":
            import re
            tokens = re.split(r'(?<=[.!?])\s+', text)
        else:
            tokens = text.split()

        result.result_data = {
            "operation": "tokenize",
            "method": method,
            "token_count": len(tokens),
            "tokens": tokens,
        }
        result.status = TaskStatus.COMPLETED

        return result

    async def _chunk_text(
        self,
        result: TaskResult,
        payload: dict[str, Any]
    ) -> TaskResult:
        """Split text into chunks for processing."""
        text = payload.get("text", "")
        chunk_size = payload.get("chunk_size", 512)
        overlap = payload.get("overlap", 50)
        method = payload.get("method", "char")  # char, word, sentence

        chunks = []

        if method == "char":
            for i in range(0, len(text), chunk_size - overlap):
                chunk = text[i:i + chunk_size]
                chunks.append(chunk)

        elif method == "word":
            words = text.split()
            for i in range(0, len(words), chunk_size - overlap):
                chunk_words = words[i:i + chunk_size]
                chunks.append(' '.join(chunk_words))

        elif method == "sentence":
            import re
            sentences = re.split(r'(?<=[.!?])\s+', text)
            current_chunk = []
            current_len = 0

            for sentence in sentences:
                if current_len + len(sentence) > chunk_size and current_chunk:
                    chunks.append(' '.join(current_chunk))
                    # Keep overlap sentences
                    overlap_count = max(1, len(current_chunk) // 4)
                    current_chunk = current_chunk[-overlap_count:]
                    current_len = sum(len(s) for s in current_chunk)

                current_chunk.append(sentence)
                current_len += len(sentence)

            if current_chunk:
                chunks.append(' '.join(current_chunk))

        result.result_data = {
            "operation": "chunk",
            "method": method,
            "chunk_size": chunk_size,
            "overlap": overlap,
            "chunk_count": len(chunks),
            "chunks": chunks,
        }
        result.status = TaskStatus.COMPLETED

        return result

    async def _extract_features(
        self,
        result: TaskResult,
        payload: dict[str, Any]
    ) -> TaskResult:
        """Extract features from text."""
        text = payload.get("text", "")

        # Basic feature extraction
        words = text.split()
        sentences = text.split('.')

        features = {
            "char_count": len(text),
            "word_count": len(words),
            "sentence_count": len(sentences),
            "avg_word_length": sum(len(w) for w in words) / max(len(words), 1),
            "avg_sentence_length": len(words) / max(len(sentences), 1),
            "unique_words": len(set(w.lower() for w in words)),
            "vocabulary_richness": len(set(w.lower() for w in words)) / max(len(words), 1),
        }

        result.result_data = {
            "operation": "extract_features",
            "features": features,
        }
        result.status = TaskStatus.COMPLETED

        return result

    async def _transform_data(
        self,
        result: TaskResult,
        payload: dict[str, Any]
    ) -> TaskResult:
        """Apply generic data transformation."""
        data = payload.get("data", {})
        transform_type = payload.get("transform_type", "identity")

        if transform_type == "identity":
            transformed = data

        elif transform_type == "flatten":
            transformed = self._flatten_dict(data)

        elif transform_type == "normalize":
            if isinstance(data, list) and all(isinstance(x, (int, float)) for x in data):
                min_val = min(data)
                max_val = max(data)
                range_val = max_val - min_val or 1
                transformed = [(x - min_val) / range_val for x in data]
            else:
                transformed = data

        else:
            transformed = data

        result.result_data = {
            "operation": "transform",
            "transform_type": transform_type,
            "transformed_data": transformed,
        }
        result.status = TaskStatus.COMPLETED

        return result

    def _flatten_dict(
        self,
        d: dict,
        parent_key: str = "",
        sep: str = "."
    ) -> dict:
        """Flatten nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)


class ModelDownloadHandler(AITaskHandler):
    """
    Handler for model download/caching tasks.

    FOG-006: Distributed model management.

    Supports:
    - Model download from registry
    - Model caching
    - Model verification
    """

    @property
    def task_type(self) -> str:
        return "model_download"

    async def execute(self, spec: TaskSpec) -> TaskResult:
        """Execute model download task."""
        start_time = datetime.now(UTC)
        result = TaskResult(
            task_id=spec.task_id,
            status=TaskStatus.RUNNING,
            started_at=start_time,
        )

        payload = spec.payload
        model_id = payload.get("model_id", "unknown")
        operation = payload.get("operation", "download")

        try:
            if operation == "download":
                result = await self._download_model(result, payload)

            elif operation == "verify":
                result = await self._verify_model(result, payload)

            elif operation == "cache_status":
                result = await self._cache_status(result, payload)

            elif operation == "clear_cache":
                result = await self._clear_cache(result, payload)

            else:
                result.status = TaskStatus.FAILED
                result.error_message = f"Unknown model operation: {operation}"
                return result

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = str(e)
            logger.error(f"Model download task {spec.task_id} failed: {e}")

        result.completed_at = datetime.now(UTC)
        result.execution_time_ms = int(
            (result.completed_at - start_time).total_seconds() * 1000
        )

        return result

    async def _download_model(
        self,
        result: TaskResult,
        payload: dict[str, Any]
    ) -> TaskResult:
        """Download a model from registry."""
        model_id = payload.get("model_id", "unknown")
        source = payload.get("source", "huggingface")
        revision = payload.get("revision", "main")

        # Simulate download
        await asyncio.sleep(0.5)  # Simulated download time

        result.result_data = {
            "operation": "download",
            "model_id": model_id,
            "source": source,
            "revision": revision,
            "status": "downloaded",
            "cache_path": f"/cache/models/{model_id}",
            "size_mb": 500,  # Placeholder
        }
        result.status = TaskStatus.COMPLETED

        return result

    async def _verify_model(
        self,
        result: TaskResult,
        payload: dict[str, Any]
    ) -> TaskResult:
        """Verify model integrity."""
        model_id = payload.get("model_id", "unknown")
        expected_hash = payload.get("expected_hash")

        # Simulate verification
        await asyncio.sleep(0.1)

        result.result_data = {
            "operation": "verify",
            "model_id": model_id,
            "verified": True,
            "hash_match": True if expected_hash else None,
            "computed_hash": "abc123def456",  # Placeholder
        }
        result.status = TaskStatus.COMPLETED

        return result

    async def _cache_status(
        self,
        result: TaskResult,
        payload: dict[str, Any]
    ) -> TaskResult:
        """Check model cache status."""
        model_id = payload.get("model_id")

        # Placeholder cache info
        result.result_data = {
            "operation": "cache_status",
            "model_id": model_id,
            "is_cached": True,
            "cache_path": f"/cache/models/{model_id}" if model_id else None,
            "cache_size_mb": 500,
            "last_accessed": datetime.now(UTC).isoformat(),
            "total_cache_size_mb": 2000,
            "available_cache_mb": 8000,
        }
        result.status = TaskStatus.COMPLETED

        return result

    async def _clear_cache(
        self,
        result: TaskResult,
        payload: dict[str, Any]
    ) -> TaskResult:
        """Clear model cache."""
        model_id = payload.get("model_id")  # None = clear all
        force = payload.get("force", False)

        # Simulate cache clearing
        await asyncio.sleep(0.1)

        result.result_data = {
            "operation": "clear_cache",
            "model_id": model_id,
            "cleared": True,
            "freed_mb": 500 if model_id else 2000,
            "remaining_cached_models": 0 if not model_id else 5,
        }
        result.status = TaskStatus.COMPLETED

        return result


# Handler registry
AI_HANDLERS: dict[str, type[AITaskHandler]] = {
    "ai_inference": AIInferenceHandler,
    "data_preprocess": DataPreprocessHandler,
    "model_download": ModelDownloadHandler,
}


def get_ai_handler(task_type: str) -> Optional[AITaskHandler]:
    """
    Get handler instance for AI task type.

    Args:
        task_type: Type of AI task

    Returns:
        Handler instance or None
    """
    handler_class = AI_HANDLERS.get(task_type)
    if handler_class:
        return handler_class()
    return None


def register_ai_handler(handler_class: type[AITaskHandler]) -> None:
    """
    Register a custom AI task handler.

    Args:
        handler_class: Handler class to register
    """
    instance = handler_class()
    AI_HANDLERS[instance.task_type] = handler_class
    logger.info(f"Registered AI handler for task type: {instance.task_type}")
