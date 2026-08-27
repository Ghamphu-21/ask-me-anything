import streamlit as st
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

st.title("Ask Me Anything 🤖")

# Keep the client alive across reruns
if "client" not in st.session_state:
    st.session_state.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Create the chat session once
if "chat" not in st.session_state:
    st.session_state.chat = st.session_state.client.chats.create(model="gemini-3.6-flash")
    st.session_state.messages = []

# Show all past messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Input box at the bottom
user_input = st.chat_input("Ask me anything...")

if user_input:
    # show user's message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # get and show bot's response
    response = st.session_state.chat.send_message(user_input)
    st.session_state.messages.append({"role": "assistant", "content": response.text})
    with st.chat_message("assistant"):
        st.write(response.text)
