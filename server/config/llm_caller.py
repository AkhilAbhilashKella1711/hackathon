from typing import Any, Dict

import litellm

import env as config
import httpx
from pydantic import BaseModel


class UnstructuredLiteLLMCompletionResponse(BaseModel):
    response: str
    completion_tokens: int
    prompt_tokens: int
    total_tokens: int
    tries: int


class LLMCaller:
    def __init__(
        self,
        payload: Dict[str, Any],
        for_validation: bool = False,
    ):
        self.payload = payload
        self.for_validation = for_validation
        self._headers = {
            'stsk': config.web_server_secret,
            'x-server-key': config.web_server_secret,
            'Content-Type': 'application/json',
        }

    async def llm_unstructured_completion(self):
        """
        Makes a POST request to the LLM service to generate a completion given a prompt.

        If not for validation, fetches the model list from the Key Vault and includes it in the payload.

        Returns
        -------
        UnstructuredLiteLLMCompletionResponse
            The response from the LLM service.
        """

        model_name = self.payload.get('model') or 'azure/gpt-4o'
        messages = self.payload.get('messages')

        # Retrieve previous chat history
        try:
            # Call LiteLLM directly
            response = await litellm.acompletion(
                api_key=config.litellm_proxy_api_key,
                base_url=str(config.litellm_proxy_api_base),
                model=model_name or 'azure/gpt-4o',
                messages=messages,
            )

            return UnstructuredLiteLLMCompletionResponse(
                response=response['choices'][0]['message']['content'],
                completion_tokens=response['usage']['completion_tokens'],
                prompt_tokens=response['usage']['prompt_tokens'],
                total_tokens=response['usage']['total_tokens'],
                tries=1,
            )
        except httpx.HTTPError as e:
            raise e