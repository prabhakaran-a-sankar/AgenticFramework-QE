"""
OpenAI LLM Implementation

This module implements the LLMInterface for OpenAI's models.
"""

import json
import logging
from typing import Dict, List, Optional, Any

import openai
from openai import AsyncOpenAI

from quality_engineering_agentic_framework.llm.llm_interface import LLMInterface
from quality_engineering_agentic_framework.utils.logger import get_logger

logger = get_logger(__name__)


def _recover_truncated_json(content: str) -> str:
    """
    Attempt to recover a JSON string that was cut off due to token limits.
    Strips the truncated tail and closes all open structures so json.loads()
    can parse whatever complete test cases were generated.
    """
    # Find the last complete test case object by locating the last '}' before
    # the outermost array closes. Strategy: find the deepest safe truncation point.
    try:
        # Try a simple parse first — maybe it's fine
        json.loads(content)
        return content
    except json.JSONDecodeError as e:
        pass

    # Truncate at the last position that had a complete object — find last '},'  or '}]'
    # Walk backwards to find a point where we can close the JSON cleanly
    cut = len(content)
    for i in range(len(content) - 1, -1, -1):
        ch = content[i]
        if ch == '}':
            candidate = content[:i+1]
            # Count open braces/brackets to figure out what closers we need
            depth_brace = candidate.count('{') - candidate.count('}')
            depth_bracket = candidate.count('[') - candidate.count(']')
            closers = (']' * depth_bracket) + ('}' * depth_brace)
            try:
                json.loads(candidate + closers)
                logger.warning(f"JSON recovery: truncated {len(content) - i - 1} chars, added closers: {repr(closers)}")
                return candidate + closers
            except json.JSONDecodeError:
                continue

    # Could not recover — return original and let the caller handle the error
    return content


class OpenAILLM(LLMInterface):
    """Implementation of LLMInterface for OpenAI."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the OpenAI LLM with configuration.
        
        Args:
            config: Dictionary containing configuration parameters
        """
        self.config = config
        self.model = config.get("model", "gpt-4")
        self.temperature = config.get("temperature", 0.2)
        self.max_tokens = config.get("max_tokens", 2000)
        
        api_key = config.get("api_key")
        if not api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = AsyncOpenAI(api_key=api_key)
        logger.info(f"Initialized OpenAI LLM with model: {self.model}")
    
    async def generate(self, 
                      prompt: str, 
                      system_message: Optional[str] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> str:
        """
        Generate text based on the prompt using OpenAI.
        
        Args:
            prompt: The prompt to send to the LLM
            system_message: Optional system message to guide the LLM
            temperature: Optional temperature parameter to override config
            max_tokens: Optional max tokens parameter to override config
            
        Returns:
            Generated text response
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            logger.error(f"Error generating text with OpenAI: {str(e)}")
            raise
    
    async def generate_with_json_output(self, 
                                       prompt: str, 
                                       json_schema: Dict[str, Any],
                                       system_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a response in JSON format according to the provided schema using OpenAI.
        
        Args:
            prompt: The prompt to send to the LLM
            json_schema: JSON schema that defines the expected output structure
            system_message: Optional system message to guide the LLM
            
        Returns:
            Generated response as a dictionary conforming to the schema
        """
        if not system_message:
            system_message = "You are a helpful assistant that responds in JSON format."
        
        system_message += f"\nYou must respond with a JSON object that conforms to this schema: {json.dumps(json_schema)}"
        
        # Ensure enough tokens for comprehensive JSON output (minimum 8000)
        json_max_tokens = max(self.max_tokens, 8000)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=json_max_tokens,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason

            if finish_reason == "length":
                logger.warning("OpenAI response was truncated (finish_reason=length). Attempting JSON recovery.")
                content = _recover_truncated_json(content)

            return json.loads(content)
        
        except Exception as e:
            logger.error(f"Error generating JSON with OpenAI: {str(e)}")
            raise
    
    def get_provider_name(self) -> str:
        """
        Get the name of the LLM provider.
        
        Returns:
            Provider name as a string
        """
        return "openai"