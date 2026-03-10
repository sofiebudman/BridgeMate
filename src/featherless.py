#!/usr/bin/env python3
"""
featherless chat helper
"""

import os
from typing import Iterator, List, Dict, Optional
from openai import OpenAI




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
	"""Build the base system prompt with user context for personalization."""
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
		"Refine your understanding before giving advice: ask 1–2 short clarifying questions when their "
		"situation is unclear (e.g., visa type, stage, family situation). Once you have context, give "
		"tailored advice. If they share details already, answer directly.\n\n"
		"Use their name when addressing them. Be conversational and empathetic. "
		"Always be supportive and encouraging.\n\n"
		f"RESPOND IN {lang_name.upper()} ONLY. This is required."
	)

	return user_context + base


def _prepare_messages(
	messages: Optional[List[Dict[str, str]]],
	user_language: Optional[str],
	user_name: Optional[str],
	user_country: Optional[str],
	k: int,
) -> List[Dict[str, str]]:
	"""Build a request-safe message list and augment user turns with retrieved context.
	Always injects a system prompt with user context (name, country, language) so the
	model can personalize responses."""
	system_content = _build_system_prompt(user_name, user_country, user_language)

	if messages is None:
		system_content = f"You are a helpful immigration interview coach assisting {user_name or 'the user'} from {user_country or 'an unspecified country'}. Your name is Bob."
		if user_language:
			system_content += f" Always respond in {user_language}."
		prepared: List[Dict[str, str]] = [
			{"role": "system", "content": system_content},
			{"role": "user", "content": "Hello"},
		]
	else:
		prepared = [m.copy() for m in messages]
		# Ensure we always have a system message with full user context
		if prepared and prepared[0].get("role") == "system":
			# Replace with our personalized system prompt so the model always has context
			prepared[0] = {"role": "system", "content": system_content}
		else:
			prepared = [{"role": "system", "content": system_content}] + prepared

	for msg in prepared:
		if msg.get("role") != "user":
			continue
		original_content = msg.get("content", "")
		retrieved_chunks = retrieve(original_content, vector_db, chunks, k=k)

		# DEBUG: show what was retrieved.
		print("=== RAG Retrieved Chunks ===")
		for i, chunk in enumerate(retrieved_chunks):
			print(f"Chunk {i + 1}:\n{chunk}\n{'-' * 40}")

		context = "\n\n".join(retrieved_chunks)
		msg["content"] = (
			f"Here is some relevant information from documents:\n{context}\n\n"
			"Use this information to answer the question, but also rely on your "
			"general knowledge to explain in understandable way if needed. Try to simplify your answers so that the info is easy to understand.\n\n"
			f"User question: {original_content}"
		)

	return prepared


def stream_featherless_chat(
	api_key: Optional[str] = None,
	model: str = "openai/gpt-oss-120b",
	max_tokens: int = 4096,
	messages: Optional[List[Dict[str, str]]] = None,
	user_language: Optional[str] = None,
	user_name: Optional[str] = None,
	user_country: Optional[str] = None,
	k: int = 3,
	prepare_messages: bool = True,
) -> Iterator[str]:
	"""Yield response tokens as they arrive from the Featherless chat API."""
	if api_key is None:
		api_key = os.getenv("FEATHERLESS_API_KEY")
	if not api_key:
		raise RuntimeError("API key not provided; set FEATHERLESS_API_KEY or pass api_key")

	client = OpenAI(base_url="https://api.featherless.ai/v1", api_key=api_key)
	prepared_messages = (
		_prepare_messages(messages=messages, user_language=user_language, user_name=user_name, user_country=user_country, k=k)
		if prepare_messages
		else (messages or [])
	)

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

def run_featherless_chat(
	api_key: Optional[str] = None,
	model: str = "openai/gpt-oss-120b",
	max_tokens: int = 1000,
	messages: Optional[List[Dict[str, str]]] = None,
	user_language: Optional[str] = None,
	user_name: Optional[str] = None,
	user_country: Optional[str] = None,
	k: int = 3,
	stream: bool = True,
) -> List[Optional[str]]:
	if api_key is None:
		api_key = os.getenv("FEATHERLESS_API_KEY")
	if not api_key:
		raise RuntimeError("API key not provided; set FEATHERLESS_API_KEY or pass api_key")
	prepared_messages = _prepare_messages(
		messages=messages,
		user_language=user_language,
		user_name=user_name,
		user_country=user_country,
		k=k,
	)

	outputs: List[Optional[str]] = []

	if stream:
		full_text = ""
		for delta in stream_featherless_chat(
			api_key=api_key,
			model=model,
			max_tokens=max_tokens,
			messages=prepared_messages,
			user_language=user_language,
			user_name=user_name,
			k=k,
			prepare_messages=False,
		):
			print(delta, end="", flush=True)
			full_text += delta

		print()
		outputs.append(full_text or None)
	else:
		client = OpenAI(base_url="https://api.featherless.ai/v1", api_key=api_key)
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
	# simple CLI helper so the test invocation can accept name/country
	import argparse
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

