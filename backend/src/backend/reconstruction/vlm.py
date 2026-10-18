import copy
import json
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import torch
from PIL import Image
from pydantic import BaseModel
from transformers import AutoProcessor, BitsAndBytesConfig, Qwen3VLForConditionalGeneration


MODEL_IDS = {
    "2b": "Qwen/Qwen3-VL-2B-Instruct",
    "4b": "Qwen/Qwen3-VL-4B-Instruct",
    "32b": "Qwen/Qwen3-VL-32B-Instruct",
    "timelens4b": "MCG-NJU/TimeLens2-4B",
}


def _device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def fit_tokens(image: np.ndarray, tokens: int) -> Image.Image:
    h, w = image.shape[:2]
    scale = (tokens * 1024 / (h * w)) ** 0.5
    width = max(32, round(w * scale / 32) * 32)
    height = max(32, round(h * scale / 32) * 32)
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    resized = cv2.resize(image, (width, height), interpolation=interpolation)
    return Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))


class QuestionVLM:
    def __init__(
        self, model: str = "timelens4b", model_path: Path | None = None, device: str | None = None,
        quantization: Literal["none", "4bit"] = "none",
        local_files_only: bool = True,
    ) -> None:
        self.name = MODEL_IDS.get(model, model)
        self.device = device or _device()
        self.quantization = quantization
        if quantization not in ("none", "4bit"):
            raise ValueError(f"Unsupported quantization: {quantization}")
        if quantization == "4bit" and (
            not self.device.startswith("cuda") or not torch.cuda.is_available()
        ):
            raise ValueError("4-bit loading requires an available CUDA GPU and CUDA-enabled PyTorch")
        model_id = str(model_path) if model_path else self.name
        dtype = torch.float32 if self.device == "cpu" else torch.bfloat16
        load_options = {"dtype": dtype, "local_files_only": local_files_only}
        if quantization == "4bit":
            load_options.update(
                device_map={"": self.device},
                quantization_config=BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=dtype,
                    bnb_4bit_use_double_quant=True,
                    # probe() reads rows of the output weights directly.
                    llm_int8_skip_modules=["lm_head"],
                ),
            )
        self._model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_id, **load_options,
        )
        if quantization == "none":
            self._model = self._model.to(self.device)
        self._model = self._model.eval()
        self._processor = AutoProcessor.from_pretrained(model_id, local_files_only=local_files_only)
        tokenizer = self._processor.tokenizer
        self._tokenizer = tokenizer
        self._pad_id = tokenizer.pad_token_id or 0
        yes = [tokenizer.encode(word)[0] for word in ("Yes", "yes", " Yes", " yes")]
        no = [tokenizer.encode(word)[0] for word in ("No", "no", " No", " no")]
        self._answer_ids = torch.tensor(sorted(set(yes)) + sorted(set(no)), device=self.device)
        self._yes_count = len(set(yes))
        self._lock = threading.Lock()

    def _image_inputs(self, image: Image.Image, text: str) -> dict:
        return self._processor(
            text=[text],
            images=[image],
            return_tensors="pt",
            images_kwargs={"size": {"shortest_edge": 1024, "longest_edge": 1 << 26}},
        ).to(self.device)

    @torch.inference_mode()
    def structured[T: BaseModel](
        self, prompt: str, schema: type[T], images: list[np.ndarray] | None = None,
        image_tokens: int = 256, max_new_tokens: int = 1024,
    ) -> T:
        content = [{"type": "image"} for _ in images or []]
        content.append({"type": "text", "text": (
            prompt + "\nReturn only a JSON object matching this schema:\n"
            + json.dumps(schema.model_json_schema())
        )})
        text = self._processor.apply_chat_template(
            [{"role": "user", "content": content}], add_generation_prompt=True,
        )
        with self._lock:
            inputs = self._processor(
                text=[text], images=[fit_tokens(image, image_tokens) for image in images] if images else None,
                return_tensors="pt",
                images_kwargs={"size": {"shortest_edge": 1024, "longest_edge": 1 << 26}},
            ).to(self.device)
            self._model.model.rope_deltas = None
            output = self._model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
            self._model.model.rope_deltas = None
            answer = self._processor.batch_decode(
                output[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True,
            )[0].strip()
        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return schema.model_validate_json(answer)

    def _prefix_text(self, context: str) -> str:
        messages = [
            {
                "role": "user",
                "content": [{"type": "image"}, {"type": "text", "text": context + "\n"}],
            }
        ]
        text = self._processor.apply_chat_template(messages, add_generation_prompt=False)
        return text[: text.rindex("<|im_end|>")]

    @torch.inference_mode()
    def probe(
        self,
        image: np.ndarray,
        questions: Sequence[str],
        context: str,
        tokens: int,
        # All of a frame's questions in one pass: every extra pass re-reads the 4-bit weights and copies
        # the image's key/value cache. 32 questions over a 256-token image need about 3 GB on 32B.
        max_batch: int = 32,
    ) -> list[float]:
        with self._lock:
            inputs = self._image_inputs(fit_tokens(image, tokens), self._prefix_text(context))
            self._model.model.rope_deltas = None
            prefix = self._model.model(**inputs, use_cache=True).past_key_values
            weights = self._model.lm_head.weight[self._answer_ids]
            result: list[float] = []
            for start in range(0, len(questions), max_batch):
                chunk = questions[start : start + max_batch]
                suffixes = [
                    self._tokenizer.encode(
                        f"Question: {question} Answer Yes or No.<|im_end|>\n"
                        "<|im_start|>assistant\n"
                    )
                    for question in chunk
                ]
                length = max(map(len, suffixes))
                ids = torch.full((len(suffixes), length), self._pad_id, dtype=torch.long)
                for row, suffix in enumerate(suffixes):
                    ids[row, : len(suffix)] = torch.tensor(suffix)
                cache = copy.deepcopy(prefix) if start + max_batch < len(questions) else prefix
                cache.batch_repeat_interleave(len(suffixes))
                hidden = self._model.model(
                    input_ids=ids.to(self.device), past_key_values=cache, use_cache=True
                ).last_hidden_state
                del cache
                last = torch.tensor([len(s) - 1 for s in suffixes], device=self.device)
                states = hidden[torch.arange(len(suffixes), device=self.device), last]
                probabilities = torch.softmax((states @ weights.T).float(), dim=-1)
                yes = probabilities[:, : self._yes_count].sum(-1)
                no = probabilities[:, self._yes_count :].sum(-1)
                result.extend((yes / (yes + no)).tolist())
            return result
