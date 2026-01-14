"""
Auto-detection of API provider based on key prefix patterns.
Add new providers here to expand platform support.
"""

# Map of key prefixes to provider names
# Ordered by specificity (more specific prefixes first)
PROVIDER_PREFIX_MAP = {
    "sk-or-": "openrouter",
    "sk-ant-": "anthropic",
    "sk-": "openai",
    "AIza": "gemini",
    "xai-": "grok",
    "gsk_": "groq",
    "mistral_": "mistral",
    "together_": "together",
    "fw-": "fireworks",
    "as-": "anyscale",
    "di_": "deepinfra",
    "neb-": "nebius",
    "nb-": "nebius",
    "co_": "cohere",
    "ai21_": "ai21",
    "aa_": "aleph_alpha",
    "r8_": "replicate",
    "bt_": "baseten",
    "modal_": "modal",
    "hf_": "huggingface",
    "pplx-": "perplexity",
    "ds_": "deepseek",
    "qwen_": "qwen",
    "glm_": "zhipu",
    "yi_": "01ai",
}


def detect_provider(api_key: str) -> str:
    """
    Auto-detect the provider from an API key based on its prefix.
    
    Args:
        api_key: The API key string to analyze
        
    Returns:
        Provider name (e.g., 'openai', 'anthropic', 'groq')
        
    Raises:
        ValueError: If the provider cannot be detected
    """
    if not api_key or not isinstance(api_key, str):
        raise ValueError("Invalid API key")
    
    api_key = api_key.strip()
    
    # Check prefixes in order (most specific first)
    for prefix, provider in PROVIDER_PREFIX_MAP.items():
        if api_key.startswith(prefix):
            return provider
    
    # If no match found
    raise ValueError(
        f"Could not detect provider from API key. "
        f"Key should start with a known prefix like: {', '.join(list(PROVIDER_PREFIX_MAP.keys())[:5])}..."
    )


def get_supported_providers() -> list[str]:
    """
    Get a list of all supported provider names.
    
    Returns:
        Sorted list of unique provider names
    """
    return sorted(set(PROVIDER_PREFIX_MAP.values()))
