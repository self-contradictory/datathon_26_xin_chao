import json
import re

import torch
from pydantic import BaseModel

from backend.reconstruction.vlm import QuestionVLM
from backend.windows.clips import Clip


def schema_suffix(schema: type[BaseModel]) -> str:
    return "\nReturn only a JSON object matching this schema:\n" + json.dumps(schema.model_json_schema())


def parse[T: BaseModel](schema: type[T], text: str) -> T:
    text = re.sub(r"^```[a-z]*\n|\n?```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("The answer contains no JSON object")
    return schema.model_validate_json(text[start:end + 1])


class WindowVLM(QuestionVLM):
    @torch.inference_mode()
    def generate(self, prompt: str, clip: Clip | None = None, max_new_tokens: int = 512) -> str:
        content = [{"type": "video"}] if clip is not None else []
        content.append({"type": "text", "text": prompt})
        text = self._processor.apply_chat_template(
            [{"role": "user", "content": content}], add_generation_prompt=True,
        )
        video = {} if clip is None else {
            "videos": [clip.frames], "video_metadata": [clip.metadata],
            "do_sample_frames": False, "do_resize": False, "cap_pixels_per_frame": False,
        }
        with self._lock:
            inputs = self._processor(text=[text], return_tensors="pt", **video).to(self.device)
            self._model.model.rope_deltas = None
            output = self._model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
            self._model.model.rope_deltas = None
            return self._processor.batch_decode(
                output[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True,
            )[0].strip()
