from flask import Flask, render_template, request, jsonify, Response
from flask_socketio import SocketIO, emit
from openai import OpenAI
from dotenv import load_dotenv
import os
import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables (if using .env)
load_dotenv()

# Load Firebase Service Account Key
cred = credentials.Certificate("ozarkchatdb-firebase-adminsdk-fbsvc-fa7c910660.json")  # Change if needed
firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()

# Initialize Flask app with WebSockets
app = Flask(__name__, static_folder="static", template_folder="templates")
socketio = SocketIO(app, cors_allowed_origins="*")  # Enable CORS for WebSocket

# Initialize OpenAI Client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Chat history to maintain memory (stores last 10 messages)
chat_history = []

# Function to get chatbot response with memory
def chat_gpt(prompt):
    try:
        # Define AI system behavior and preload business info
        system_instructions = {
            "role": "system",
            "content": """
            You are Ozark Poop Patrol’s customer service assistant.
            Your goal is to get their name and phone number so they can talk to a real Specialist—always try to ask.
            Your job is to answer customer questions professionally, using the provided business information.
            Always be polite, accurate, and helpful. If you don't know something, say so.

            **Business Information:**
            - **Company Name:** Ozark Poop Patrol
            - **Phone:** 303-988-2317
            - **Email:** info@ozarkpoopatrol.com
            - **Address:** Eighth Avenue 487, New York
            - **Service Areas:** Springfield, Nixa, Ozark, Branson
            - **Pricing & Services:**
              - Ultimate Lawn Sanitization: $22.86 per week (includes bug treatment & deodorization, first week free)
              - Green Yard Scoop Away: $13.62 per week
              - One-Time Cleanup: $49 per cleanup
            - **Policies:** No cat litter, secure gates, first service is free.

            If a customer seems unsure, remind them of the "No Poop Left Behind Guarantee!"
            """
        }

        # Combine system instructions with chat history
        full_chat = [system_instructions] + chat_history + [{"role": "user", "content": prompt}]

        # Call OpenAI with chat history
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=full_chat
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {str(e)}"

# WebSocket event handler for chat
@socketio.on('message')
def handle_message(data):
    global chat_history

    # Get user input and session_id
    user_input = data.get('message', '')
    session_id = data.get('session_id', '')

    if not user_input or not session_id:
        emit('response', {'bot_response': 'No input provided'})
        return

    # Store user message in Firestore (chat_logs)
    chat_log_ref = db.collection("chat_logs").document()
    chat_log_ref.set({
        "session_id": session_id,
        "user_message": user_input,
        "timestamp": datetime.datetime.utcnow()
    })

    # Get chatbot response
    response = chat_gpt(user_input)

    # Store bot response in Firestore
    chat_log_ref.update({"bot_response": response})

    # Emit response to frontend
    emit('response', {'bot_response': response})

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat')
def chat():
    return render_template('chat.html')  # Ensure chat.html exists in /templates

@app.route('/test-firestore')
def test_firestore():
    test_doc_ref = db.collection("chat_sessions").document("test_connection")
    test_doc_ref.set({"message": "Firestore is connected!", "status": "Success"})
    return {"status": "success", "message": "Firestore write test successful"}

@app.route('/create-session', methods=['POST'])
def create_session():
    data = request.json

    # Generate a new session document
    session_ref = db.collection("chat_sessions").document()
    session_id = session_ref.id  # Firestore auto-generated ID

    # Prepare session data
    session_data = {
        "ip_address": data.get("ip_address", "Unknown"),
        "device_type": data.get("device_type", "Unknown"),
        "operating_system": data.get("operating_system", "Unknown"),
        "browser": data.get("browser", "Unknown"),
        "timestamp": datetime.datetime.utcnow()
    }

    # Save to Firestore
    session_ref.set(session_data)

    return jsonify({"status": "success", "session_id": session_id})

@app.route('/get-messages', methods=['POST'])
def get_messages():
    data = request.json
    session_id = data.get("session_id", "")

    if not session_id:
        return jsonify({"status": "error", "message": "No session ID provided"}), 400

    try:
        # Query Firestore for chat logs with the given session_id, ordered by timestamp
        messages = db.collection("chat_logs").where("session_id", "==", session_id).order_by("timestamp").stream()
        
        chat_history = []
        for msg in messages:
            msg_data = msg.to_dict()
            chat_history.append({
                "user_message": msg_data.get("user_message", ""),
                "bot_response": msg_data.get("bot_response", ""),
                "timestamp": msg_data.get("timestamp", "")
            })

        return jsonify({"status": "success", "chat_history": chat_history})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/chat-widget")
def chat_widget():
    return render_template("chat-widget.html")  # This file will contain only the chat widget


@app.route("/embed.js")
def serve_embed_js():
    script = """
    (function() {
        function loadChat() {
            if (document.getElementById('ozark-chat-widget')) return; // Prevent duplicate loading

            var chatContainer = document.createElement('div');
            chatContainer.id = 'ozark-chat-widget';
            chatContainer.style.position = 'fixed';
            chatContainer.style.bottom = '20px';
            chatContainer.style.right = '20px';
            chatContainer.style.width = '350px';
            chatContainer.style.height = '500px';
            chatContainer.style.border = 'none';
            chatContainer.style.zIndex = '9999';
            chatContainer.style.boxShadow = '0 4px 8px rgba(0,0,0,0.2)';
            chatContainer.style.borderRadius = '10px';
            chatContainer.style.overflow = 'hidden';
            chatContainer.style.backgroundColor = 'white';

            var chatFrame = document.createElement('iframe');
            chatFrame.src = 'http://localhost:5000/chat-widget';  // Now loads only the widget
            chatFrame.style.width = '100%';
            chatFrame.style.height = '100%';
            chatFrame.style.border = 'none';

            chatContainer.appendChild(chatFrame);
            document.body.appendChild(chatContainer);
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', loadChat);
        } else {
            loadChat();
        }
    })();
    """
    return Response(script, mimetype="application/javascript")



if __name__ == '__main__':
    socketio.run(app, debug=True)
