from openai import OpenAI
import time


class LLM_interface:
    def __init__(self, model_name = "gpt-4.1"):
        self.api_keys = ''
        self.model_name = model_name
        print("bulid openai client")
        self.client = OpenAI(api_key="", base_url="https://api.openai.com/v1")
        
    def dialog(self, prompt, temperature = -1.0, max_retries=3, timeout=30):
        temperature = 0.8

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=prompt,
                    stream=False,
                    temperature = temperature,
                    timeout=timeout
                )
                
                if response is None:
                    print("⚠️ API 返回 None")
                    return ""
                else:
                    res = response.choices[0].message.content
                    return res
                    
            except Exception as e:
                attempt_num = attempt + 1
                print(f"⚠️ 第{attempt_num}次调用API出现问题，原因是: {e}")
                
                # 如果不是最后一次尝试，等待一段时间后重试
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  
                    print(f"⏳ {wait_time}秒后进行第{attempt_num + 1}次重试...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ 已重试{max_retries}次，调用API失败")
                    return ''
        
        return ''
    

import os
import base64
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.identity import (
    ChainedTokenCredential,
    AzureCliCredential,
    ManagedIdentityCredential
)
        

class LLM_interface_Azure:
    def __init__(self,endpoint=None,deployment=None,api_version=None,isTRAPI=False):
        self.isTRAPI = isTRAPI
        if isTRAPI:
            # TRAPI 配置
            host = os.environ.get(
                "TRAPI_HOST",
                "https://trapi.research.microsoft.com"
            )

            self.endpoint = endpoint or os.environ.get(
                "AZURE_OPENAI_ENDPOINT",
                f"{host}/redmond/interactive"
            )

            self.deployment = deployment or os.environ.get(
                "OPENAI_MODEL",
                "gpt-5_2025-08-07"
            )

            api_version = api_version or os.environ.get(
                "OPENAI_API_VERSION",
                "2025-04-01-preview"
            )

            token_provider = get_bearer_token_provider(
                ChainedTokenCredential(
                    AzureCliCredential(),
                    ManagedIdentityCredential()
                ),
                "api://trapi/.default"
            )

        else:
            # 普通 Azure OpenAI 配置
            self.endpoint = endpoint or os.environ.get(
                "AZURE_OPENAI_ENDPOINT",
                "https://gcraoai6sw1.openai.azure.com/"
            )

            self.deployment = deployment or os.environ.get(
                "OPENAI_MODEL",
                "gpt-5.5_2026-04-24"
            )

            api_version = api_version or os.environ.get(
                "OPENAI_API_VERSION",
                "2025-01-01-preview"
            )

            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default"
            )

        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            azure_ad_token_provider=token_provider,
            api_version=api_version,
        )

    def dialog(self, prompt, temperature=0.8, max_retries=3, timeout=30):
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=prompt,
                    stream=False,
                    timeout=timeout
                )

                if response is None:
                    print("⚠️ API 返回 None")
                    return ""

                return response.choices[0].message.content or ""

            except Exception as e:
                attempt_num = attempt + 1
                print(f"⚠️ 第{attempt_num}次调用API出现问题，原因是: {e}")

                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"⏳ {wait_time}秒后进行第{attempt_num + 1}次重试...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ 已重试{max_retries}次，调用API失败")
                    return ""

        return ""
