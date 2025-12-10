# ...existing code...
import streamlit as st
try:
    import google.generativeai as genai
except Exception:
    genai = None

class ChatbotService:
    def __init__(self):
        # read Gemini API key from streamlit secrets
        try:
            self.api_key = st.secrets['GEMINI_API_KEY']
        except Exception:
            self.api_key = None
            print("Gemini key not found in st.secrets (use GEMINI_API_KEY)")

        # configure client if library available
        if genai and self.api_key:
            try:
                # some versions require genai.configure, others do not — ignore errors
                genai.configure(api_key=self.api_key)
            except Exception as e:
                print("Failed to configure Gemini client (or configure not required):", e)

        # system instruction to keep responses safe
        self.system_prompt = (
            "You are a helpful home health assistant. Provide first-aid steps and safe advice. "
            "Do NOT give medical diagnoses or prescribe medications. For emergencies, instruct to call local emergency services."
        )

    def ask(self, user_text, context=None, model="gemini-2.5-flash"):
        if not self.api_key or not genai:
            return "Chatbot API key or Gemini client not configured. Please set GEMINI_API_KEY in .streamlit/secrets.toml and install/upgrade google-generativeai."

        context_text = ""
        if context:
            # context: dict with temp, hum, gas, ai, ts, device
            ctx_parts = []
            for k in ("ts","device","ai","temp","hum","gas"):
                if k in context and context[k] is not None:
                    ctx_parts.append(f"{k}: {context[k]}")
            context_text = "\n".join(ctx_parts)

        prompt = f"{context_text}\n\nUser: {user_text}"

        messages = [
            {"author": "system", "content": self.system_prompt},
            {"author": "user", "content": prompt}
        ]

        try:
            # Prepare common kwargs
            call_kwargs = dict(model=model, messages=messages, max_output_tokens=350, temperature=0.2)

            # Try multiple call shapes for compatibility across genai versions
            resp = None
            if hasattr(genai, "chat") and hasattr(genai.chat, "create"):
                resp = genai.chat.create(**call_kwargs)
            elif hasattr(genai, "ChatCompletion") and hasattr(genai.ChatCompletion, "create"):
                resp = genai.ChatCompletion.create(**call_kwargs)
            elif hasattr(genai, "models") and hasattr(genai.models, "generate"):
                # genai.models.generate in some releases accepts 'messages'
                try:
                    resp = genai.models.generate(**call_kwargs)
                except Exception:
                    # fallback: some variants expect 'input' or 'prompt' instead of 'messages'
                    resp = genai.models.generate(model=model, prompt=prompt, max_output_tokens=350, temperature=0.2)
            elif hasattr(genai, "generate"):
                try:
                    resp = genai.generate(**call_kwargs)
                except Exception:
                    resp = genai.generate(model=model, prompt=prompt, max_output_tokens=350, temperature=0.2)
            else:
                raise RuntimeError("Installed google.generativeai package doesn't expose a known chat/generate API. Try upgrading with: pip install --upgrade google-generativeai")

            # robust extraction of text from possible response shapes
            text = ""
            try:
                # primary common shape: resp.candidates[0].content[0].text
                text = resp.candidates[0].content[0].text
            except Exception:
                try:
                    # alternate convenience property
                    text = getattr(resp, "output_text", "") or getattr(resp, "result", "")
                except Exception:
                    # last resort: string representation
                    text = str(resp)

            return (text or "").strip()
        except Exception as e:
            print("Chatbot (Gemini) error:", e)
            return f"Chatbot error: {e}"
# ...existing code...