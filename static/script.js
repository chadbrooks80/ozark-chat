document.addEventListener("DOMContentLoaded", function () {
    var chatIcon = document.getElementById("chat-icon");
    var chatContainer = document.getElementById("chat-container");
    var closeChat = document.getElementById("close-chat");
    var sendBtn = document.getElementById("send-btn");
    var userInput = document.getElementById("user-input");
    var chatMessages = document.getElementById("chat-messages");
    var socket = io(); // Connect to WebSocket

    // ✅ Session Expiration Time (CHANGE THIS FOR TESTING)
    const SESSION_EXPIRATION_MINUTES = 1440; // 🔥 1440 minutes = 24 hours (Change to 1 for testing)

    // ✅ Function to get session_id from cookies
    function getSessionId() {
        return document.cookie.split('; ').find(row => row.startsWith('session_id='))?.split('=')[1];
    }

    // ✅ Function to set session_id in cookies with expiration time
    function setSessionId(sessionId) {
        let expires = new Date();
        expires.setMinutes(expires.getMinutes() + SESSION_EXPIRATION_MINUTES);
        document.cookie = `session_id=${sessionId}; expires=${expires.toUTCString()}; path=/`;
        console.log(`⏳ Session expiration updated: ${SESSION_EXPIRATION_MINUTES} minutes from now`);
    }

    let sessionId = getSessionId(); // Get session from cookies

    // ✅ Open chatbox and create session if needed
    chatIcon.addEventListener("click", function () {
        chatContainer.classList.add("show");
        chatIcon.style.display = "none"; 
        userInput.focus();

        if (!sessionId) {
            fetch("/create-session", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({})
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === "success") {
                    sessionId = data.session_id;
                    setSessionId(sessionId); // Store session in cookies
                    console.log("🔥 New session created:", sessionId);
                }
            })
            .catch(error => console.error("Error creating session:", error));
        } else {
            console.log("✅ Existing session loaded from cookies:", sessionId);
            loadChatHistory(); // ✅ Load previous chat messages
        }
    });

    // ✅ Function to load chat history from Firestore
    function loadChatHistory() {
        console.log("🔄 Loading chat history for session:", sessionId);

        fetch("/get-messages", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId })
        })
        .then(response => response.json())
        .then(data => {
            console.log("💬 Chat history response:", data); // Debugging output

            if (data.status === "success") {
                chatMessages.innerHTML = ""; // ✅ Clear chat box before loading history
                data.chat_history.forEach(msg => {
                    if (msg.user_message) {
                        console.log("📤 User message found:", msg.user_message);
                        var userMessage = document.createElement("div");
                        userMessage.classList.add("message", "user-message");
                        userMessage.innerHTML = `<p>🐾 ${msg.user_message}</p>`;
                        chatMessages.appendChild(userMessage);
                    }
                    if (msg.bot_response) {
                        console.log("🤖 Bot response found:", msg.bot_response);
                        var botMessage = document.createElement("div");
                        botMessage.classList.add("message", "bot-message");
                        botMessage.innerHTML = `<p>🐶 ${msg.bot_response}</p>`;
                        chatMessages.appendChild(botMessage);
                    }
                });
                chatMessages.scrollTop = chatMessages.scrollHeight; // ✅ Scroll to bottom
            } else {
                console.log("⚠️ No chat history found.");
            }
        })
        .catch(error => console.error("❌ Error loading chat history:", error));
    }

    // ✅ Function to send message
    function sendMessage() {
        var input = userInput.value.trim();
        if (input === "" || !sessionId) return;

        // Append User Message
        var userMessage = document.createElement("div");
        userMessage.classList.add("message", "user-message");
        userMessage.innerHTML = `<p>🐾 ${input}</p>`;
        chatMessages.appendChild(userMessage);

        // ✅ Update session expiration each time a message is sent
        setSessionId(sessionId);

        // Send message to server via WebSocket
        socket.emit("message", { session_id: sessionId, message: input });

        userInput.value = ""; // Clear input field
        userInput.focus();
    }

    // ✅ Send message when "Send" button is clicked
    sendBtn.addEventListener("click", sendMessage);

    // ✅ Send message when "Enter" key is pressed
    userInput.addEventListener("keypress", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            sendMessage();
        }
    });

    // ✅ Listen for bot responses
    socket.on("response", function (data) {
        var botMessage = document.createElement("div");
        botMessage.classList.add("message", "bot-message");
        botMessage.innerHTML = `<p>🐶 ${data.bot_response}</p>`;
        chatMessages.appendChild(botMessage);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });

    // ✅ Fix for Close Button Issue
    closeChat.addEventListener("click", function () {
        chatContainer.classList.remove("show"); // ✅ Hide chat window
        setTimeout(() => {
            chatIcon.style.display = "block"; // ✅ Bring back chat icon
        }, 300); // Matches CSS transition duration
    });
});
