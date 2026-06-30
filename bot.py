import os
import io
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from ics import Calendar, Event
from ics.icalendar import Calendar as ICalCalendar

# Get token from environment variable
TOKEN = os.environ.get("BOT_TOKEN", "")

if not TOKEN:
    print("❌ ERROR: BOT_TOKEN environment variable not set!")
    print("Please add BOT_TOKEN in Railway Variables tab")
    exit(1)

print(f"✅ Token loaded successfully (length: {len(TOKEN)})")

# User state storage
user_data = {}

# ===== Helper Functions =====
def create_calendar(events_data):
    """Create an ICS calendar from event data"""
    calendar = Calendar()
    
    for event_data in events_data:
        event = Event()
        event.name = event_data.get('name', 'Untitled Event')
        event.begin = datetime.fromisoformat(event_data.get('start', datetime.now().isoformat()))
        
        if event_data.get('end'):
            event.end = datetime.fromisoformat(event_data['end'])
        else:
            # Default to 1 hour duration
            event.end = event.begin + timedelta(hours=1)
        
        if event_data.get('description'):
            event.description = event_data['description']
        if event_data.get('location'):
            event.location = event_data['location']
        
        calendar.events.add(event)
    
    return calendar

def generate_ics_file(calendar):
    """Generate ICS file content"""
    return str(calendar)

# ===== Command Handlers =====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    welcome_msg = (
        f"📅 *Hello {user.first_name}!*\n\n"
        "Welcome to *iCalendar Generator Bot* - your calendar creation companion!\n\n"
        "I can help you create iCalendar (.ics) files that you can import into:\n"
        "• Google Calendar\n"
        "• Apple Calendar\n"
        "• Microsoft Outlook\n"
        "• And any other calendar app!\n\n"
        "*How to use:*\n"
        "1️⃣ Use /addevent to add events to your calendar\n"
        "2️⃣ Use /listevents to see your current events\n"
        "3️⃣ Use /generate to create your .ics file\n"
        "4️⃣ Use /clear to start over\n\n"
        "Send /help to see all commands."
    )
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    # Initialize user data
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {'events': []}

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_msg = (
        "📖 *iCalendar Generator Bot Help*\n\n"
        "*Commands:*\n"
        "/start - Welcome message\n"
        "/help - Show this help\n"
        "/addevent - Add an event to your calendar\n"
        "/listevents - List all your events\n"
        "/generate - Generate and download .ics file\n"
        "/clear - Clear all your events\n"
        "/about - About this bot\n\n"
        "*How to add an event:*\n"
        "1. Send /addevent\n"
        "2. Follow the prompts to enter event details\n\n"
        "*Example event data:*\n"
        "• Name: Team Meeting\n"
        "• Start: 2026-07-01 14:00\n"
        "• End: 2026-07-01 15:00\n"
        "• Description: Weekly sync (optional)\n"
        "• Location: Conference Room (optional)"
    )
    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /about command"""
    about_msg = (
        "📅 *About iCalendar Generator Bot*\n\n"
        "This bot creates iCalendar (.ics) files from your events.\n\n"
        "*Features:*\n"
        "✓ Add multiple events\n"
        "✓ Set start and end times\n"
        "✓ Add descriptions and locations\n"
        "✓ Generate standard .ics files\n"
        "✓ Compatible with all calendar apps\n"
        "✓ Privacy-focused (we don't store your data)\n"
        "✓ Free to use\n\n"
        "Built with ❤️ using python-telegram-bot and ics libraries."
    )
    await update.message.reply_text(about_msg, parse_mode='Markdown')

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command"""
    user_id = update.effective_user.id
    if user_id in user_data:
        user_data[user_id]['events'] = []
        await update.message.reply_text("✅ All your events have been cleared!")
    else:
        await update.message.reply_text("⚠️ You don't have any events to clear.")

async def add_event_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addevent command - start event creation flow"""
    user_id = update.effective_user.id
    
    # Initialize user data if not exists
    if user_id not in user_data:
        user_data[user_id] = {'events': []}
    
    # Set user state to 'adding_event'
    user_data[user_id]['state'] = 'adding_event_name'
    user_data[user_id]['new_event'] = {}
    
    await update.message.reply_text(
        "📝 *Add New Event*\n\n"
        "Please enter the *event name* (e.g., 'Team Meeting'):\n\n"
        "Type /cancel to cancel adding this event.",
        parse_mode='Markdown'
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command"""
    user_id = update.effective_user.id
    if user_id in user_data and 'state' in user_data[user_id]:
        del user_data[user_id]['state']
        if 'new_event' in user_data[user_id]:
            del user_data[user_id]['new_event']
        await update.message.reply_text("✅ Event creation cancelled.")
    else:
        await update.message.reply_text("⚠️ You're not currently adding an event.")

async def list_events_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /listevents command"""
    user_id = update.effective_user.id
    
    if user_id not in user_data or not user_data[user_id]['events']:
        await update.message.reply_text("📭 You don't have any events yet. Use /addevent to add one!")
        return
    
    events = user_data[user_id]['events']
    event_list = []
    for i, event in enumerate(events, 1):
        event_list.append(
            f"{i}. *{event.get('name', 'Untitled')}*\n"
            f"   📅 {event.get('start', 'No start time')}\n"
            f"   ⏰ {event.get('end', 'No end time')}"
        )
    
    response = (
        f"📋 *Your Events ({len(events)})*\n\n"
        + "\n".join(event_list)
        + "\n\n💡 Use /generate to create your .ics file!"
    )
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /generate command - create and send ICS file"""
    user_id = update.effective_user.id
    
    if user_id not in user_data or not user_data[user_id]['events']:
        await update.message.reply_text(
            "⚠️ You don't have any events to generate a calendar!\n"
            "Use /addevent to add some events first."
        )
        return
    
    try:
        # Create calendar
        calendar = create_calendar(user_data[user_id]['events'])
        ics_content = generate_ics_file(calendar)
        
        # Create file in memory
        ics_file = io.BytesIO(ics_content.encode('utf-8'))
        ics_file.name = "calendar.ics"
        
        # Send the file
        await update.message.reply_document(
            document=ics_file,
            filename="calendar.ics",
            caption="📅 *Your Calendar*\n\nHere's your .ics file. You can import it into any calendar app!\n\n"
                    f"• *Events:* {len(user_data[user_id]['events'])}\n"
                    "• *Format:* iCalendar (.ics)\n\n"
                    "📥 Click the file to download it.",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        print(f"Generate error: {e}")
        await update.message.reply_text(f"⚠️ Error generating calendar: {str(e)}")

# ===== Message Handler for Event Creation Flow =====
async def handle_event_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages during event creation flow"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id not in user_data or 'state' not in user_data[user_id]:
        return
    
    state = user_data[user_id]['state']
    
    # Handle cancellation
    if text.lower() == '/cancel':
        await cancel_command(update, context)
        return
    
    try:
        if state == 'adding_event_name':
            user_data[user_id]['new_event']['name'] = text
            user_data[user_id]['state'] = 'adding_event_start'
            await update.message.reply_text(
                "📅 *Event Name Set*\n\n"
                f"Event: *{text}*\n\n"
                "Now enter the *start date and time* (e.g., '2026-07-01 14:00'):\n\n"
                "Format: `YYYY-MM-DD HH:MM` (24-hour)",
                parse_mode='Markdown'
            )
            
        elif state == 'adding_event_start':
            try:
                start = datetime.strptime(text, '%Y-%m-%d %H:%M')
                user_data[user_id]['new_event']['start'] = start.isoformat()
                user_data[user_id]['state'] = 'adding_event_end'
                await update.message.reply_text(
                    "✅ *Start time set*\n\n"
                    f"Start: *{start.strftime('%Y-%m-%d %H:%M')}*\n\n"
                    "Now enter the *end date and time* (e.g., '2026-07-01 15:00'):\n\n"
                    "Format: `YYYY-MM-DD HH:MM` (24-hour)",
                    parse_mode='Markdown'
                )
            except ValueError:
                await update.message.reply_text(
                    "⚠️ Invalid format! Please use `YYYY-MM-DD HH:MM`\n"
                    "Example: `2026-07-01 14:00`",
                    parse_mode='Markdown'
                )
                
        elif state == 'adding_event_end':
            try:
                end = datetime.strptime(text, '%Y-%m-%d %H:%M')
                user_data[user_id]['new_event']['end'] = end.isoformat()
                user_data[user_id]['state'] = 'adding_event_description'
                await update.message.reply_text(
                    "✅ *End time set*\n\n"
                    f"End: *{end.strftime('%Y-%m-%d %H:%M')}*\n\n"
                    "Now enter a *description* (or type 'skip' to skip):",
                    parse_mode='Markdown'
                )
            except ValueError:
                await update.message.reply_text(
                    "⚠️ Invalid format! Please use `YYYY-MM-DD HH:MM`\n"
                    "Example: `2026-07-01 15:00`",
                    parse_mode='Markdown'
                )
                
        elif state == 'adding_event_description':
            if text.lower() != 'skip':
                user_data[user_id]['new_event']['description'] = text
            user_data[user_id]['state'] = 'adding_event_location'
            await update.message.reply_text(
                "✅ *Description set*\n\n"
                f"Description: *{text if text.lower() != 'skip' else 'None'}*\n\n"
                "Finally, enter a *location* (or type 'skip' to skip):",
                parse_mode='Markdown'
            )
            
        elif state == 'adding_event_location':
            if text.lower() != 'skip':
                user_data[user_id]['new_event']['location'] = text
            
            # Save the event
            event_data = user_data[user_id]['new_event']
            user_data[user_id]['events'].append(event_data)
            
            # Clear state
            del user_data[user_id]['state']
            del user_data[user_id]['new_event']
            
            await update.message.reply_text(
                f"✅ *Event Added Successfully!*\n\n"
                f"📋 *Event Details:*\n"
                f"• *Name:* {event_data.get('name', 'Untitled')}\n"
                f"• *Start:* {event_data.get('start', 'N/A')}\n"
                f"• *End:* {event_data.get('end', 'N/A')}\n"
                f"• *Description:* {event_data.get('description', 'None')}\n"
                f"• *Location:* {event_data.get('location', 'None')}\n\n"
                f"You now have {len(user_data[user_id]['events'])} event(s).\n"
                f"Add more with /addevent or generate your calendar with /generate!",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        print(f"Event creation error: {e}")
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

# ===== Error Handler =====
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    print(f"❌ Error: {context.error}")
    try:
        if update and update.message:
            await update.message.reply_text("⚠️ An error occurred. Please try again.")
    except:
        pass

# ===== Main Function =====
def main():
    """Start the bot"""
    print("🚀 Starting iCalendar Generator Bot...")
    
    try:
        application = Application.builder().token(TOKEN).build()
        print("✅ Application built successfully")
        
        # Command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("about", about_command))
        application.add_handler(CommandHandler("addevent", add_event_command))
        application.add_handler(CommandHandler("listevents", list_events_command))
        application.add_handler(CommandHandler("generate", generate_command))
        application.add_handler(CommandHandler("clear", clear_command))
        application.add_handler(CommandHandler("cancel", cancel_command))
        
        # Message handler for event creation flow
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_event_creation))
        
        # Error handler
        application.add_error_handler(error_handler)
        
        print("✅ Bot is running! Waiting for messages...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    main()
