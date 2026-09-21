import itertools
import streamlit as st
import os
import httpx
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

MODEL = "gemini-3.6-flash"

# a persona is just a different system instruction, add a new one by adding a line here
PERSONAS = {
    "Default": "You are a helpful, friendly assistant.",
    "Motivational Coach": "You are an energetic motivational coach. Be upbeat and encouraging, turn problems into action steps, and keep answers short and punchy.",
    "Roaster": "You are a savage but playful roast comedian. Nitpick every typo, grammar slip, and flaw in the user's message and tease them about it in a funny way. Mock their mistakes and questions, never their identity, appearance, background, or anything genuinely personal. Keep it lighthearted, and still give the correct answer at the end.",
    "Sarcastic Friend": "You are a witty friend with dry, light sarcasm. Tease gently, never be rude or hurtful, and always give a genuinely helpful answer.",
    "Explain Like I'm Five": "Explain everything in very simple words with everyday analogies, as if talking to a five-year-old.",
    "Strict Professor": "You are a strict but fair college professor. Be precise and formal, push the student to think, and correct sloppy reasoning.",
    "Code Reviewer": "You are a senior software engineer doing code review. Point out bugs, bad practices, and improvements, explain why each matters, and suggest a fixed version.",
}

STARTER_QUESTIONS = [
    "Tell me a joke",
    "Explain quantum physics like I'm five",
    "Give me a fun fact about space",
]

# this has to be the very first streamlit call or it throws an error
st.set_page_config(page_title="Ask Me Anything", page_icon="🤖")

st.title("Ask Me Anything 🤖")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("GEMINI_API_KEY not found. Add it to your .env file and restart the app.")
    st.stop()


def new_chat():
    # clears the screen AND makes a new Gemini chat, otherwise it would still remember the old messages
    persona = st.session_state.get("persona", "Default")
    st.session_state.chat = st.session_state.client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=PERSONAS[persona]),
    )
    st.session_state.messages = []


def get_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    elif 17 <= hour < 21:
        return "Good evening"
    else:
        return "Hello, night owl"


def text_chunks(stream):
    # gemini sometimes sends empty chunks, skip those
    for chunk in stream:
        if chunk.text:
            yield chunk.text


def friendly_error(e):
    # turns scary exceptions into something a normal person can read
    if isinstance(e, errors.APIError):
        if e.code == 429:
            return "⏳ Rate limit reached. Please wait a minute and try again."
        if e.code in (400, 401, 403):
            return "🔑 There's a problem with the API key or the request. Check your .env file."
        if e.code >= 500:
            return "🛠️ Gemini's servers are having trouble right now. Please try again shortly."
        return f"Gemini returned an error (code {e.code}). Please try again."
    if isinstance(e, (httpx.ConnectError, httpx.TimeoutException)):
        return "📡 Can't reach Gemini. Check your internet connection and try again."
    return "Something went wrong. Please try again."


def chat_to_text():
    # plain text version of the conversation for the export button
    lines = [
        "Ask Me Anything - Chat Log",
        f"Persona: {st.session_state.get('persona', 'Default')}",
        f"Exported: {datetime.now().strftime('%d %b %Y, %H:%M')}",
        "-" * 40,
        "",
    ]
    for msg in st.session_state.messages:
        who = "You" if msg["role"] == "user" else "Bot"
        lines.append(f"{who}: {msg['content']}")
        lines.append("")
    return "\n".join(lines)


# streamlit reruns this whole file on every click, so the client and chat
# live in session_state or they'd be recreated (and forgotten) each time.
# retries only for 5xx errors: retrying a 429 just burns more of the quota
if "client" not in st.session_state:
    st.session_state.client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                attempts=4,
                http_status_codes=[500, 502, 503, 504],
            )
        ),
    )

if "chat" not in st.session_state:
    new_chat()

# redraw the old messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# greeting + starter buttons, only shown while the chat is empty.
# they sit in a placeholder so I can wipe them the moment a message is sent
prompt = None
chips = st.empty()

if not st.session_state.messages:
    with chips.container():
        st.subheader(f"{get_greeting()}! How can I help you today?")
        st.caption("Try asking:")
        for q in STARTER_QUESTIONS:
            if st.button(q):
                prompt = q

# typed message wins, otherwise use whichever starter button was clicked
typed = st.chat_input("Ask me anything...")
prompt = typed or prompt

if prompt:
    chips.empty()

    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        try:
            # the spinner only lasts until the first bit of text arrives
            with st.spinner("Thinking..."):
                stream = st.session_state.chat.send_message_stream(prompt)
                chunks = text_chunks(stream)
                first = next(chunks, None)

            if first is None:
                reply = "I couldn't generate a response for that. Try rephrasing."
                st.write(reply)
            else:
                # put the first chunk back in front, then stream the whole thing live
                reply = st.write_stream(itertools.chain([first], chunks))

            # only save once the reply worked, so a failed request
            # doesn't leave a question in the history with no answer
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.messages.append({"role": "assistant", "content": reply})

        except Exception as e:
            # full error goes to the terminal for debugging, friendly one goes on screen
            print(f"[ERROR] {type(e).__name__}: {e}")
            st.error(friendly_error(e))

# sidebar is at the bottom on purpose. if it ran earlier, the export
# button would always be one message behind
with st.sidebar:
    st.header("Options")

    # changing persona starts a new chat because the persona is set when the chat is created
    st.selectbox("Persona", list(PERSONAS.keys()), key="persona", on_change=new_chat)
    st.caption("Changing persona starts a new chat.")

    if st.button("🗑️ Clear chat"):
        new_chat()
        st.rerun()

    st.download_button(
        "⬇️ Export chat",
        data=chat_to_text(),
        file_name=f"chat_log_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain",
        disabled=not st.session_state.messages,
    )
