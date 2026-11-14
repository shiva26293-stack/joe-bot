import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from groq import Groq
import edge_tts

# Retrieve keys safely from Cloud Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """You are Joe, a warm, patient, and encouraging native English speaker and conversation partner.
Rules:
1. Keep replies short (1 to 3 sentences maximum) so we have a realistic conversation.
2. Always end your reply with an engaging question to keep me speaking.
3. If I make a grammar, word choice, or phrasing mistake, gently provide the correction at the very beginning in brackets like this:
   [Correction: '...']
   Then continue the conversation naturally as Joe.
"""

conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_text = ""

        # Voice note handler
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

        # Text message handler
        elif update.message.text:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            user_text = update.message.text

        if not user_text:
            return

        conversation_history.append({"role": "user", "content": user_text})

        # Joe thinks
        chat_completion = groq_client.chat.completions.create(
            messages=conversation_history,
            model="openai/gpt-oss-120b",
        )
        ai_reply = chat_completion.choices[0].message.content
        conversation_history.append({"role": "assistant", "content": ai_reply})

        # Joe speaks
        output_audio = f"reply_{update.message.id}.mp3"
        tts = edge_tts.Communicate(ai_reply, voice="en-US-ChristopherNeural")
        await tts.save(output_audio)

        # Send back to Telegram
        with open(output_audio, "rb") as audio:
            await update.message.reply_voice(voice=audio, caption=ai_reply)

        if os.path.exists(output_audio):
            os.remove(output_audio)

    except Exception as e:
        print(f"Error: {e}")

# Fake web server to satisfy Render's free tier health checks
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
    # Start web server thread
    threading.Thread(target=run_web_server, daemon=True).start()

    # Start Telegram Bot
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.VOICE | filters.TEXT, handle_message))
    print("Joe is running in the cloud!")
    app.run_polling()
