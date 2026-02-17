import os
import openai
import anthropic
try:
    import ollama
except ImportError:
    ollama = None
import logging
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt, model=None):
        pass

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
    
    def generate(self, prompt, model="claude-3-sonnet-20240229"):
            message = self.client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            if not message.content or len(message.content) == 0:
                raise ValueError("Empty response from Anthropic API")
            return message.content[0].text

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key)

    def generate(self, prompt, model="gpt-4-turbo-preview"):
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024
            )
            if not response.choices or len(response.choices) == 0:
                raise ValueError("Empty response from OpenAI API")
            return response.choices[0].message.content

class OllamaProvider(LLMProvider):
    def __init__(self):
        if ollama is None:
            logging.warning("Ollama library not installed. Local models will not work.")
    
    def generate(self, prompt, model="gemma2:latest"):
        if ollama is None:
            raise ImportError("Ollama library not installed. Please install it with `pip install ollama`.")
            
        try:
            response = ollama.chat(model=model, messages=[
                {'role': 'user', 'content': prompt},
            ])
            if not response or 'message' not in response or 'content' not in response['message']:
                raise ValueError(f"Invalid response format from Ollama for model '{model}'")
            return response['message']['content']
        except Exception as e:
            # Re-raise with a clear message for the UI
            if isinstance(e, (ValueError, ImportError)):
                raise
            raise ConnectionError(f"Ollama Error: {str(e)}. Ensure 'ollama serve' is running and model '{model}' is pulled.")

class LLMGenerator:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("Prisma.LLMGenerator")
        self.providers = {}
        self._initialize_providers(config)
    
    def _initialize_providers(self, config):
        """Initialize or reinitialize providers based on config."""
        # Initialize providers based on available keys/config
        anthropic_key = config.get('llm', {}).get('api_keys', {}).get('anthropic')
        if anthropic_key:
            try:
                self.providers['anthropic'] = AnthropicProvider(anthropic_key)
            except Exception as e:
                self.logger.warning(f"Failed to initialize Anthropic provider: {e}")
        
        openai_key = config.get('llm', {}).get('api_keys', {}).get('openai')
        if openai_key:
            try:
                self.providers['openai'] = OpenAIProvider(openai_key)
            except Exception as e:
                self.logger.warning(f"Failed to initialize OpenAI provider: {e}")
            
        self.providers['ollama'] = OllamaProvider()
    
    def update_api_key(self, provider, api_key):
        """Update API key for a provider and reinitialize it."""
        if provider == 'anthropic' and api_key:
            self.providers['anthropic'] = AnthropicProvider(api_key)
            if 'llm' not in self.config:
                self.config['llm'] = {}
            if 'api_keys' not in self.config['llm']:
                self.config['llm']['api_keys'] = {}
            self.config['llm']['api_keys']['anthropic'] = api_key
        elif provider == 'openai' and api_key:
            self.providers['openai'] = OpenAIProvider(api_key)
            if 'llm' not in self.config:
                self.config['llm'] = {}
            if 'api_keys' not in self.config['llm']:
                self.config['llm']['api_keys'] = {}
            self.config['llm']['api_keys']['openai'] = api_key

    def generate_insights(self, dataset_summary, prompt_template_name="basic", model_provider="anthropic", model_name=None):
        """
        Generates insights using the specified provider and prompt strategy.
        """
        # Handle import path - works both from root and from src directory
        try:
            from utils import load_prompts
        except ImportError:
            from src.utils import load_prompts
        
        prompts = load_prompts()
        if prompt_template_name not in prompts:
            self.logger.error(f"Prompt template '{prompt_template_name}' not found.")
            return None
            
        prompt = prompts[prompt_template_name].format(dataset_summary=str(dataset_summary))
        
        provider = self.providers.get(model_provider)
        if not provider:
            self.logger.error(f"Provider '{model_provider}' not initialized.")
            return None
        
        # Use default model from config if model_name is None
        if model_name is None:
            model_name = self.config.get('llm', {}).get('default_model', None)
            if model_name is None:
                # Provider-specific defaults
                if model_provider == "anthropic":
                    model_name = "claude-3-sonnet-20240229"
                elif model_provider == "openai":
                    model_name = "gpt-4-turbo-preview"
                elif model_provider == "ollama":
                    model_name = "gemma:2b"
            
        self.logger.info(f"Generating insights with {model_provider} using model {model_name}...")
        try:
            response = provider.generate(prompt, model=model_name)
            return response
        except Exception as e:
            self.logger.error(f"Error generating insights: {str(e)}")
            raise
