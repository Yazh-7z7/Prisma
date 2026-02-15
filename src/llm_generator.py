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
        try:
            message = self.client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            logging.error(f"Anthropic API error: {e}")
            return None

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key)

    def generate(self, prompt, model="gpt-4-turbo-preview"):
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"OpenAI API error: {e}")
            return None

class OllamaProvider(LLMProvider):
    def __init__(self):
        if ollama is None:
            logging.warning("Ollama library not installed. Local models will not work.")
    
    def generate(self, prompt, model="gemma2:latest"):
        if ollama is None:
            return "Ollama not available."
        try:
            response = ollama.chat(model=model, messages=[
                {'role': 'user', 'content': prompt},
            ])
            return response['message']['content']
        except Exception as e:
            logging.error(f"Ollama API error: {e}")
            return None

class LLMGenerator:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("Prisma.LLMGenerator")
        self.providers = {}
        
        # Initialize providers based on available keys/config
        if config['llm']['api_keys'].get('anthropic'):
            self.providers['anthropic'] = AnthropicProvider(config['llm']['api_keys']['anthropic'])
        
        if config['llm']['api_keys'].get('openai'):
            self.providers['openai'] = OpenAIProvider(config['llm']['api_keys']['openai'])
            
        self.providers['ollama'] = OllamaProvider()

    def generate_insights(self, dataset_summary, prompt_template_name="basic", model_provider="anthropic", model_name=None):
        """
        Generates insights using the specified provider and prompt strategy.
        """
        from utils import load_prompts
        
        prompts = load_prompts()
        if prompt_template_name not in prompts:
            self.logger.error(f"Prompt template '{prompt_template_name}' not found.")
            return None
            
        prompt = prompts[prompt_template_name].format(dataset_summary=str(dataset_summary))
        
        provider = self.providers.get(model_provider)
        if not provider:
            self.logger.error(f"Provider '{model_provider}' not initialized.")
            return None
            
        self.logger.info(f"Generating insights with {model_provider}...")
        response = provider.generate(prompt, model=model_name)
        return response
