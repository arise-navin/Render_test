
# import requests

# OLLAMA_URL = "http://localhost:11434/api/generate"
# MODEL = "devstral-2:123b-cloud"

# def ask_llm(prompt):
#     r = requests.post(
#         OLLAMA_URL,
#         json={"model": MODEL, "prompt": prompt, "stream": False}
#     )
#     return r.json().get("response", "")

import os
from openai import OpenAI

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "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")
MODEL = "mistralai/devstral-2-123b-instruct-2512"
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
)


def ask_llm(prompt: str, temperature: float = 0.15, top_p: float = 0.95, max_tokens: int = 4096) -> str:
    """
    Send a prompt to the NVIDIA-hosted Devstral model and return the full response as a string.
    Uses streaming internally for reliability, but collects all chunks before returning.
    """
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        stream=True,
    )

    result = []
    for chunk in completion:
        if chunk.choices and chunk.choices[0].delta.content:
            result.append(chunk.choices[0].delta.content)

    return "".join(result)