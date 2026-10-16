"""LLM providers behind one tiny interface: chat(messages, max_tokens) -> str.

  openai : OpenAI API (the class setup). Key from config.json "openaiKey" or env OPENAI_API_KEY.
  local  : a small model running on this machine via llama.cpp (no key, no cost).
  auto   : openai if a key is configured, otherwise local.
"""
import json
import os
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")

DEFAULTS = {
    "provider": "auto",
    "openaiKey": "",
    "openaiModel": "gpt-4o",
    "localModelPath": "models/qwen2.5-coder-3b-instruct-q4_k_m.gguf",
}


def load_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    if os.environ.get("OPENAI_API_KEY"):
        cfg["openaiKey"] = os.environ["OPENAI_API_KEY"]
    if os.environ.get("LLM_PROVIDER"):
        cfg["provider"] = os.environ["LLM_PROVIDER"]
    key = cfg.get("openaiKey", "")
    if not key or "replace" in key.lower():
        cfg["openaiKey"] = ""
    return cfg


class OpenAIProvider:
    def __init__(self, api_key, model):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.name = f"OpenAI {model}"
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}

    def chat(self, messages, max_tokens=600):
        r = self.client.chat.completions.create(model=self.model, messages=messages,
                                                temperature=0, max_tokens=max_tokens)
        if r.usage:
            self.usage["prompt_tokens"] += r.usage.prompt_tokens
            self.usage["completion_tokens"] += r.usage.completion_tokens
        return r.choices[0].message.content or ""


class LocalProvider:
    def __init__(self, model_path):
        from llama_cpp import Llama
        path = model_path if os.path.isabs(model_path) else os.path.join(HERE, model_path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Local model not found at {path}. See README for the download command.")
        # llama.cpp prints Metal init chatter straight to fd 2; hide it while loading
        saved = os.dup(2)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
        try:
            self.llm = Llama(model_path=path, n_ctx=8192, n_gpu_layers=-1, verbose=False)
        finally:
            os.dup2(saved, 2)
            os.close(saved)
            os.close(devnull)
        # Remember processed prompt prefixes (the long schema block) across calls, so only the new
        # question has to be read each time even though the answer step runs in between.
        from llama_cpp import LlamaRAMCache
        self.llm.set_cache(LlamaRAMCache(capacity_bytes=1 << 30))
        self.name = f"local {os.path.basename(path)}"
        self.lock = threading.Lock()  # llama.cpp contexts are not thread-safe
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}

    def chat(self, messages, max_tokens=600):
        with self.lock:
            r = self.llm.create_chat_completion(messages=messages, temperature=0, max_tokens=max_tokens,
                                                repeat_penalty=1.1)
        u = r.get("usage") or {}
        self.usage["prompt_tokens"] += u.get("prompt_tokens", 0)
        self.usage["completion_tokens"] += u.get("completion_tokens", 0)
        return r["choices"][0]["message"]["content"] or ""


def make_provider(cfg=None):
    cfg = cfg or load_config()
    provider = cfg["provider"]
    if provider == "auto":
        provider = "openai" if cfg["openaiKey"] else "local"
    if provider == "openai":
        if not cfg["openaiKey"]:
            raise RuntimeError("provider is 'openai' but no key: put it in config.json or set OPENAI_API_KEY")
        return OpenAIProvider(cfg["openaiKey"], cfg["openaiModel"])
    if provider == "local":
        return LocalProvider(cfg["localModelPath"])
    raise ValueError(f"unknown provider {provider!r}")
