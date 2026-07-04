import os
import io
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from PIL import Image

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

user_images: dict[int, bytes] = {}


def get_action_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("↔️ Flip Horizontal", callback_data="flip_h"),
            InlineKeyboardButton("↕️ Flip Vertical", callback_data="flip_v"),
        ],
        [
            InlineKeyboardButton("↩️ Rotate 90°", callback_data="rotate_90"),
            InlineKeyboardButton("🔄 Rotate 180°", callback_data="rotate_180"),
        ],
        [
            InlineKeyboardButton("↪️ Rotate 270°", callback_data="rotate_270"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Welcome to the Image Flip/Rotate Bot!\n\n"
        "📸 Simply send me any image, and I'll let you:\n"
        "• Flip it horizontally or vertically\n"
        "• Rotate it by 90°, 180°, or 270°\n\n"
        "Go ahead — send me a photo!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ℹ️ *How to use this bot:*\n\n"
        "1. Send any photo or image file\n"
        "2. Choose an action from the buttons\n"
        "3. Receive your transformed image!\n\n"
        "You can keep applying transformations to the same image.",
        parse_mode="Markdown",
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    buf = io.BytesIO()
    await file.download_to_memory(buf)
    user_images[user_id] = buf.getvalue()
    await update.message.reply_text(
        "✅ Image received! Choose an action:",
        reply_markup=get_action_keyboard(),
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    doc = update.message.document
    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        await update.message.reply_text("⚠️ Please send an image file (JPEG, PNG, WEBP, etc.)")
        return
    file = await context.bot.get_file(doc.file_id)
    buf = io.BytesIO()
    await file.download_to_memory(buf)
    user_images[user_id] = buf.getvalue()
    await update.message.reply_text(
        "✅ Image received! Choose an action:",
        reply_markup=get_action_keyboard(),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if user_id not in user_images:
        await query.edit_message_text("⚠️ No image found. Please send a photo first.")
        return

    action = query.data
    image_bytes = user_images[user_id]

    try:
        img = Image.open(io.BytesIO(image_bytes))

        if action == "flip_h":
            result = img.transpose(Image.FLIP_LEFT_RIGHT)
            caption = "↔️ Flipped horizontally"
        elif action == "flip_v":
            result = img.transpose(Image.FLIP_TOP_BOTTOM)
            caption = "↕️ Flipped vertically"
        elif action == "rotate_90":
            result = img.transpose(Image.ROTATE_90)
            caption = "↩️ Rotated 90°"
        elif action == "rotate_180":
            result = img.transpose(Image.ROTATE_180)
            caption = "🔄 Rotated 180°"
        elif action == "rotate_270":
            result = img.transpose(Image.ROTATE_270)
            caption = "↪️ Rotated 270°"
        else:
            await query.edit_message_text("⚠️ Unknown action.")
            return

        out_buf = io.BytesIO()
        fmt = img.format or "PNG"
        result.save(out_buf, format=fmt)
        out_buf.seek(0)
        user_images[user_id] = out_buf.getvalue()

        out_buf.seek(0)
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=out_buf,
            caption=f"{caption}\n\nApply another transformation:",
            reply_markup=get_action_keyboard(),
        )

    except Exception as e:
        logger.error(f"Image processing error: {e}")
        await query.edit_message_text(
            "❌ Failed to process the image. Please try sending it again."
        )


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    webhook_url = os.environ.get("WEBHOOK_URL")
    port = int(os.environ.get("PORT", 8443))

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))

    if webhook_url:
        logger.info(f"Starting webhook on port {port}")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=f"{webhook_url}/webhook",
            url_path="/webhook",
        )
    else:
        logger.info("Starting polling (local dev mode)")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
