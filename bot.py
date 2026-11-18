import os
import asyncio
import threading
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from groq import Groq
import edge_tts

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

# ==========================================
# PROMPTS FOR MODES
# ==========================================
PROMPTS = {
    "normal": """You are a warm, patient, and encouraging native English speaker and conversation partner named Joe.
Rules:
1. Keep replies short (1 to 3 sentences maximum) for natural back-and-forth dialogue.
2. Always end your reply with an engaging question to keep the user speaking.
3. If the user makes any grammar, phrasing, or vocabulary error, gently provide the correction at the beginning in brackets: [Correction: '...']. Then continue naturally.""",

    "interview": """You are an experienced job interviewer named Joe.
Rules:
1. Conduct a realistic job interview. Ask one interview question at a time.
2. If the user makes a grammar or phrasing mistake, put [Correction: '...'] at the start, then react professionally and ask the next question.
3. Keep responses concise (under 3 sentences).""",

    "travel": """You are Joe, roleplaying as local service staff (airport officer, cafe barista, hotel receptionist).
Rules:
1. Stay in character! Keep the roleplay realistic, helpful, and interactive.
2. Keep replies short (1 to 2 sentences) and prompt the user for their next response.
3. Put corrections in brackets at the start: [Correction: '...'].""",

    "debate": """You are Joe, an intellectual and friendly debate partner.
Rules:
1. Challenge the user's opinions respectfully to help them practice arguing in English.
2. Keep replies under 3 sentences, make a counter-argument, and ask what they think.
3. Put corrections in brackets at the start: [Correction: '...']."""
}

user_sessions = {}

def get_user_data(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "mode": "normal",
            "voice": "en-IN-PrabhatNeural",  # Default to Indian Male
            "rate": "+0%",
            "history": [{"role": "system", "content": PROMPTS["normal"]}],
            "mistakes": []
        }
    return user_sessions[user_id]

# ==========================================
# CLICKABLE BUTTONS MENU
# ==========================================
def build_menu_keyboard():
    keyboard = [
        # Practice Modes
        [
            InlineKeyboardButton("🎯 Casual", callback_data="mode_normal"),
            InlineKeyboardButton("💼 Interview", callback_data="mode_interview")
        ],
        [
            InlineKeyboardButton("✈️ Travel Roleplay", callback_data="mode_travel"),
            InlineKeyboardButton("⚖️ Debate Topic", callback_data="mode_debate")
        ],
        # Voices
        [
            InlineKeyboardButton("🇮🇳 Indian (Male)", callback_data="voice_in_m"),
            InlineKeyboardButton("🇮🇳 Indian (Female)", callback_data="voice_in_f")
        ],
        [
            InlineKeyboardButton("🇺🇸 US (Male)", callback_data="voice_us_m"),
            InlineKeyboardButton("🇺🇸 US (Female)", callback_data="voice_us_f")
        ],
        [
            InlineKeyboardButton("🇬🇧 UK (Male)", callback_data="voice_uk_m"),
            InlineKeyboardButton("🇦🇺 Aussie (Male)", callback_data="voice_au_m")
        ],
        # Speed
        [
            InlineKeyboardButton("🐢 Slower", callback_data="speed_slow"),
            InlineKeyboardButton("🚶 Normal", callback_data="speed_normal"),
            InlineKeyboardButton("⚡ Faster", callback_data="speed_fast")
        ],
        # Actions
        [
            InlineKeyboardButton("📊 Get My Summary", callback_data="action_summary"),
            InlineKeyboardButton("🔄 Reset Chat", callback_data="action_reset")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎛️ **Joe's Control Panel**\n\n"
        "Tap any button below to adjust your settings, or just send a voice note to talk!"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=build_menu_keyboard(), parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=build_menu_keyboard(), parse_mode="Markdown")

# ==========================================
# BUTTON CLICK HANDLER
# ==========================================
async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = get_user_data(user_id)
    choice = query.data

    # Modes
    if choice.startswith("mode_"):
        mode = choice.replace("mode_", "")
        data["mode"] = mode
        data["history"] = [{"role": "system", "content": PROMPTS[mode]}]
        names = {
            "normal": "🎯 Casual Conversation mode is active! How's your day going?",
            "interview": "💼 Interview Prep mode is active! What job role are you interviewing for?",
            "travel": "✈️ Travel mode is active! *Ding dong* 'Welcome to the airport! May I see your ticket?'",
            "debate": "⚖️ Debate mode is active! Topic: 'Is remote work better than working from an office?' Your turn!"
        }
        await query.message.reply_text(names[mode])

    # Voices
    elif choice == "voice_in_m":
        data["voice"] = "en-IN-PrabhatNeural"
        await query.message.reply_text("🇮🇳 Voice set to **Indian English (Male - Prabhat)**!", parse_mode="Markdown")
    elif choice == "voice_in_f":
        data["voice"] = "en-IN-NeerjaNeural"
        await query.message.reply_text("🇮🇳 Voice set to **Indian English (Female - Neerja)**!", parse_mode="Markdown")
    elif choice == "voice_us_m":
        data["voice"] = "en-US-GuyNeural"
        await query.message.reply_text("🇺🇸 Voice set to **American English (Male - Guy)**!", parse_mode="Markdown")
    elif choice == "voice_us_f":
        data["voice"] = "en-US-JennyNeural"
        await query.message.reply_text("🇺🇸 Voice set to **American English (Female - Jenny)**!", parse_mode="Markdown")
    elif choice == "voice_uk_m":
        data["voice"] = "en-GB-RyanNeural"
        await query.message.reply_text("🇬🇧 Voice set to **British English (Male - Ryan)**!", parse_mode="Markdown")
    elif choice == "voice_au_m":
        data["voice"] = "en-AU-WilliamNeural"
        await query.message.reply_text("🇦🇺 Voice set to **Australian English (Male - William)**!", parse_mode="Markdown")

    # Speeds
    elif choice == "speed_slow":
        data["rate"] = "-15%"
        await query.message.reply_text("🐢 Voice speed set to **Slow** (-15%)!", parse_mode="Markdown")
    elif choice == "speed_normal":
        data["rate"] = "+0%"
        await query.message.reply_text("🚶 Voice speed set to **Normal**!", parse_mode="Markdown")
    elif choice == "speed_fast":
        data["rate"] = "+15%"
        await query.message.reply_text("⚡ Voice speed set to **Fast** (+15%)!", parse_mode="Markdown")

    # Reset
    elif choice == "action_reset":
        data["history"] = [{"role": "system", "content": PROMPTS[data["mode"]]}]
        data["mistakes"] = []
        await query.message.reply_text("🔄 Chat history cleared. Ready for a fresh start!")

    # Summary
    elif choice == "action_summary":
        if not data["mistakes"]:
            await query.message.reply_text("You haven't made any recorded mistakes yet. Send a few voice notes first!")
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        mistakes_text = "\n".join(f"- {m}" for m in data["mistakes"][-6:])
        prompt = f"""Based on these mistakes the user made during practice:
{mistakes_text}

Generate a short, encouraging recap:
1. Review the top 2-3 mistakes with easy explanations.
2. Introduce 2 advanced, natural English idioms they can use tomorrow.
Keep it concise and clear."""

        completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-oss-120b",
        )
        summary = completion.choices[0].message.content
        await query.message.reply_text(f"📊 **Your Practice Summary:**\n\n{summary}", parse_mode="Markdown")

# ==========================================
# SUMMARY COMMAND
# ==========================================
async def send_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = get_user_data(user_id)
    if not data["mistakes"]:
        await update.message.reply_text("You haven't made any recorded mistakes yet. Send a few voice notes first!")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    mistakes_text = "\n".join(f"- {m}" for m in data["mistakes"][-6:])
    prompt = f"""Based on these mistakes the user made during practice:
{mistakes_text}

Generate a short, encouraging recap:
1. Review the top 2-3 mistakes with easy explanations.
2. Introduce 2 advanced, natural English idioms they can use tomorrow.
Keep it concise and clear."""

    completion = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="openai/gpt-oss-120b",
    )
    summary = completion.choices[0].message.content
    await update.message.reply_text(f"📊 **Your Practice Summary:**\n\n{summary}", parse_mode="Markdown")

# ==========================================
# VOICE & TEXT MESSAGE PROCESSING
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        data = get_user_data(user_id)
        user_text = ""

        # Voice Note
        if update.message.voice:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
            voice_file = await update.message.voice.get_file()
            input_audio = f"user_{update.message.id}.ogg"
            await voice_file.download_to_drive(input_audio)

            with open(input_audio, "rb") as audio:
                transcription = groq_client.audio.transcriptions.create(
                    file=(input_audio, audio.read()),
                    model="whisper-large-v3",
                    language="en"
                )
            user_text = transcription.text
            if os.path.exists(input_audio):
                os.remove(input_audio)

        # Text Message
        elif update.message.text:
            if update.message.text.lower() in ["menu", "help", "options", "settings"]:
                await show_menu(update, context)
                return
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            user_text = update.message.text

        if not user_text:
            return

        data["history"].append({"role": "user", "content": user_text})

        # AI brain response
        chat_completion = groq_client.chat.completions.create(
            messages=data["history"],
            model="openai/gpt-oss-120b",
        )
        ai_reply = chat_completion.choices[0].message.content
        data["history"].append({"role": "assistant", "content": ai_reply})

        # Save corrections
        corrections = re.findall(r"\[Correction:.*?\]", ai_reply)
        for c in corrections:
            data["mistakes"].append(f"You said: '{user_text}' -> {c}")

        # Generate Speech
        output_audio = f"reply_{update.message.id}.mp3"
        tts = edge_tts.Communicate(ai_reply, voice=data["voice"], rate=data["rate"])
        await tts.save(output_audio)

        # Send voice note back
        with open(output_audio, "rb") as audio:
            await update.message.reply_voice(voice=audio, caption=ai_reply)

        if os.path.exists(output_audio):
            os.remove(output_audio)

    except Exception as e:
        print(f"Error: {e}")

# ==========================================
# REGISTER BOT MENU BUTTON IN TELEGRAM
# ==========================================
async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("menu", "🎛️ Control Panel (Voices & Modes)"),
        BotCommand("summary", "📊 Daily Mistakes & Idioms"),
        BotCommand("start", "🚀 Start / Welcome")
    ])

# Web server for Render health checks
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Joe is alive and running 24/7!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()

    # Build bot with persistent Menu button setup
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", show_menu))
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CommandHandler("summary", send_summary))
    app.add_handler(CallbackQueryHandler(handle_button_click))
    app.add_handler(MessageHandler(filters.VOICE | filters.TEXT, handle_message))
    
    print("Joe is running with native Menu button!")
    app.run_polling()
