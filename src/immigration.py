import os
from typing import Iterator, List, Dict, Optional
from openai import OpenAI

from featherless import run_featherless_chat, stream_featherless_chat
import argparse


#TODO: ask questions before launching chat where the user fills out a form with buttons to say where they are immigrating from + basic information and to the context of the system prompt
#precode to introduce it self and before you begin it uses a form to ask the user a few questions to fill out context and customize exprience 
from rag import vector_db, chunks, retrieve
from env_loader import load_env_file


load_env_file()


def _build_system_prompt(
	user_name: Optional[str],
	user_country: Optional[str],
	user_language: Optional[str],
) -> str:
	"""Build the interview coaching system prompt with user context for personalization."""
	name = (user_name and user_name.strip()) or "the user"
	country = (user_country and user_country.strip()) or "an unspecified country"
	LANG_NAMES = {
		"en": "English", "es": "Spanish", "fr": "French", "de": "German",
		"it": "Italian", "pt": "Portuguese", "ru": "Russian", "ja": "Japanese",
		"zh": "Chinese", "ko": "Korean", "ar": "Arabic", "hi": "Hindi",
	}
	lang_name = LANG_NAMES.get(user_language or "", user_language or "English")

	# Put user context at the very top so the model cannot miss it
	user_context = (
		"=== USER PROFILE (use this in every response) ===\n"
		f"- Name: {name}\n"
		f"- Country of origin: {country}\n"
		f"- Preferred language: {lang_name}\n"
		"Address the user by name. Tailor advice to their country when relevant. Always respond in their preferred language.\n\n"
	)

	base = (
		"You are a helpful immigration interview coach. "
		f"You are assisting {name}, who is from {country}, in their immigration journey to the United States.\n\n"
		"Help prepare for an interview by asking 1 interview question at a time. These questions should simulate a real immigration interview situation After they answer, give feedback on their answer and then ask the next question. "
       
		f"RESPOND IN {lang_name.upper()} ONLY. This is required."
	)

	return user_context + base


def stream_interview_chat(
	api_key: Optional[str] = None,
	model: str = "openai/gpt-oss-120b",
	max_tokens: int = 4096,
	messages: Optional[List[Dict[str, str]]] = None,
	user_language: Optional[str] = None,
	user_name: Optional[str] = None,
	user_country: Optional[str] = None,
) -> Iterator[str]:
	"""Yield response tokens as they arrive from the Featherless chat API for interview mode."""
	if api_key is None:
		api_key = os.getenv("FEATHERLESS_API_KEY")
	if not api_key:
		raise RuntimeError("API key not provided; set FEATHERLESS_API_KEY or pass api_key")

	client = OpenAI(base_url="https://api.featherless.ai/v1", api_key=api_key)
	
	# Use the interview system prompt
	system_content = _build_system_prompt(user_name, user_country, user_language)
	
	prepared_messages = [{"role": "system", "content": system_content}]
	if messages:
		# Skip any existing system message and use ours
		prepared_messages.extend([m.copy() for m in messages if m.get("role") != "system"])
	else:
		prepared_messages.append({"role": "user", "content": "Hello"})

	resp_stream = client.chat.completions.create(
		model=model,
		max_tokens=max_tokens,
		messages=prepared_messages,
		stream=True,
	)

	for event in resp_stream:
		choices = getattr(event, "choices", None)
		if choices is None and isinstance(event, dict):
			choices = event.get("choices", [])
		if not choices:
			continue

		first_choice = choices[0]
		delta = ""
		try:
			delta = first_choice.delta.content or ""
		except Exception:
			try:
				delta = first_choice.get("delta", {}).get("content", "")
			except Exception:
				delta = ""

		if delta:
			yield delta


def run_interview_chat(
	api_key: Optional[str] = None,
	model: str = "openai/gpt-oss-120b",
	max_tokens: int = 1000,
	messages: Optional[List[Dict[str, str]]] = None,
	user_language: Optional[str] = None,
	user_name: Optional[str] = None,
	user_country: Optional[str] = None,
	stream: bool = True,
) -> List[Optional[str]]:
	"""Run interview chat and return response as a list of strings."""
	if api_key is None:
		api_key = os.getenv("FEATHERLESS_API_KEY")
	if not api_key:
		raise RuntimeError("API key not provided; set FEATHERLESS_API_KEY or pass api_key")

	outputs: List[Optional[str]] = []

	if stream:
		full_text = ""
		for delta in stream_interview_chat(
			api_key=api_key,
			model=model,
			max_tokens=max_tokens,
			messages=messages,
			user_language=user_language,
			user_name=user_name,
			user_country=user_country,
		):
			print(delta, end="", flush=True)
			full_text += delta

		print()
		outputs.append(full_text or None)
	else:
		client = OpenAI(base_url="https://api.featherless.ai/v1", api_key=api_key)
		
		# Use the interview system prompt
		system_content = _build_system_prompt(user_name, user_country, user_language)
		
		prepared_messages = [{"role": "system", "content": system_content}]
		if messages:
			# Skip any existing system message and use ours
			prepared_messages.extend([m.copy() for m in messages if m.get("role") != "system"])
		else:
			prepared_messages.append({"role": "user", "content": "Hello"})
		
		resp = client.chat.completions.create(
			model=model,
			max_tokens=max_tokens,
			messages=prepared_messages,
		)
		for choice in getattr(resp, "choices", []) or resp.get("choices", []):
			content = None
			try:
				content = choice.message.content
			except Exception:
				try:
					content = choice["message"]["content"]
				except Exception:
					content = None
			outputs.append(content)
			print(content)

	return outputs

if __name__ == "__main__":
	# Example usage
	parser = argparse.ArgumentParser(description="Test Featherless chat helper")
	parser.add_argument("--name", default="User", help="name of the user")
	parser.add_argument("--country", default="US", help="country code of the user")
	parser.add_argument("--language", default=None, help="user preferred language")
	args = parser.parse_args()
	# run a simple request to verify everything works
	run_featherless_chat(
		user_name=args.name,
		user_country=args.country,
		user_language=args.language,
		k=3,
	)