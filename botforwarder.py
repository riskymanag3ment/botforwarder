#!/usr/bin/env python3
"""
Telegram Bot Message Forwarder - Command Line Version
Usage: python telegram_forwarder.py --bot-token <token> --channel <channel_id> [options]
"""

import argparse
import asyncio
import json
import os
import requests
import sys
import time
from datetime import datetime
from pathlib import Path
from telethon.sessions import StringSession
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

# Configuration
TELEGRAM_API_URL = "https://api.telegram.org/bot"
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 1  # seconds between requests
RATE_LIMIT_BURST_DELAY = 30  # seconds to wait when hitting rate limits
MAX_BATCH_SIZE = 100  # messages per batch

class TelegramForwarder:
    def __init__(self, bot_token, channel_id, output_dir="captured_messages"):
        self.bot_token = self.parse_bot_token(bot_token)
        self.channel_id = channel_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Telegram client setup
        self.api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
        self.api_hash = os.getenv("TELEGRAM_API_HASH", "")
        self.phone_number = os.getenv("TELEGRAM_PHONE", "")
        self.session_string = os.getenv("TELEGRAM_SESSION", "")

        if not all([self.api_id, self.api_hash, self.phone_number]):
            print("❌ Missing Telegram credentials in environment variables:")
            print("   TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE")
            sys.exit(1)

        # Use session from file if .env doesn't have it
        if not self.session_string:
            self.session_string = self.load_session_from_file()

        session = StringSession(self.session_string) if self.session_string else StringSession()

        self.client = TelegramClient(
            session,
            self.api_id,
            self.api_hash,
            app_version="9.4.0"
        )

        # State tracking
        self.bot_username = None
        self.my_chat_id = None
        self.last_message_id = None
        self.session = requests.Session()
        self.rate_limit_count = 0
        self.last_request_time = 0

        # File paths
        self.data_file = self.output_dir / f"bot_{self.bot_token.split(':')[0]}_channel_{self.channel_id}_messages.json"
        self.log_file = self.output_dir / f"bot_{self.bot_token.split(':')[0]}_channel_{self.channel_id}_log.txt"
        self.session_file = self.output_dir / f"telegram_session_{self.bot_token.split(':')[0]}.txt"

    def save_session_string(self, session_string):
        """Save session string to file and update .env if it exists"""
        try:
            # Save to dedicated session file
            with open(self.session_file, "w", encoding="utf-8") as f:
                f.write(session_string)
            self.log(f"💾 Session saved to {self.session_file}")

            # Try to update .env file if it exists
            env_file = Path(".env")
            if env_file.exists():
                self.update_env_file(session_string)
            else:
                self.log("📝 No .env file found. Create one with:")
                self.log(f"TELEGRAM_SESSION={session_string}")

        except Exception as e:
            self.log(f"❌ Failed to save session: {e}", "ERROR")

    def update_env_file(self, session_string):
        """Update the .env file with the new session string"""
        try:
            env_file = Path(".env")
            lines = []
            session_updated = False

            if env_file.exists():
                with open(env_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()

            # Update existing TELEGRAM_SESSION line or add new one
            for i, line in enumerate(lines):
                if line.strip().startswith("TELEGRAM_SESSION="):
                    lines[i] = f"TELEGRAM_SESSION={session_string}\n"
                    session_updated = True
                    break

            if not session_updated:
                lines.append(f"\nTELEGRAM_SESSION={session_string}\n")

            # Write back to file
            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

            self.log("📝 Updated .env file with new session string")

        except Exception as e:
            self.log(f"❌ Failed to update .env file: {e}", "ERROR")

    def load_session_from_file(self):
        """Load session string from file if .env doesn't have it"""
        if self.session_string:
            return self.session_string

        try:
            if self.session_file.exists():
                with open(self.session_file, "r", encoding="utf-8") as f:
                    session_string = f.read().strip()
                if session_string:
                    self.log("📂 Loaded session from file")
                    return session_string
        except Exception as e:
            self.log(f"⚠️ Failed to load session from file: {e}", "WARN")

    def parse_bot_token(self, raw_token):
        """Clean and validate bot token"""
        raw_token = raw_token.strip()
        if raw_token.lower().startswith("bot"):
            raw_token = raw_token[3:]
        return raw_token

    def log(self, message, level="INFO"):
        """Log message to console and file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_message + "\n")
        except Exception as e:
            print(f"❌ Failed to write to log file: {e}")

    def handle_rate_limit(self):
        """Handle rate limiting with exponential backoff"""
        current_time = time.time()
        if current_time - self.last_request_time < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY)

        self.last_request_time = time.time()

        if self.rate_limit_count > 10:  # Too many requests
            self.log(f"⏳ Rate limit hit, waiting {RATE_LIMIT_BURST_DELAY} seconds...", "WARN")
            time.sleep(RATE_LIMIT_BURST_DELAY)
            self.rate_limit_count = 0

    async def authenticate_bot(self):
        """Authenticate bot and get basic info"""
        # Validate bot token
        url = f"{TELEGRAM_API_URL}{self.bot_token}/getMe"
        try:
            response = requests.get(url)
            data = response.json()

            if not data.get("ok"):
                self.log(f"❌ Bot token validation failed: {data}", "ERROR")
                return False

            bot_info = data["result"]
            self.bot_username = bot_info.get("username")
            self.log(f"✅ Bot authenticated: @{self.bot_username}")

        except Exception as e:
            self.log(f"❌ Failed to validate bot token: {e}", "ERROR")
            return False

        # Initialize Telegram client with OTP
        try:
            await self.client.start(phone=self.phone_number)
            self.log("✅ Telegram client authenticated")

            # Save session string automatically
            session_string = self.client.session.save()
            if not self.session_string or self.session_string != session_string:
                self.save_session_string(session_string)
                self.log("💾 Session string saved/updated automatically")

            # Send /start to bot
            if not self.bot_username.startswith("@"):
                bot_username = "@" + self.bot_username
            else:
                bot_username = self.bot_username

            await self.client.send_message(bot_username, "/start")
            self.log(f"✅ Sent /start to {bot_username}")
            await asyncio.sleep(2)

        except Exception as e:
            self.log(f"❌ Telegram client authentication failed: {e}", "ERROR")
            return False

        return True

    def get_my_chat_info(self):
        """Get chat info after sending /start"""
        url = f"{TELEGRAM_API_URL}{self.bot_token}/getUpdates"
        try:
            response = requests.get(url)
            data = response.json()

            if data.get("ok") and data["result"]:
                last_update = data["result"][-1]
                if "message" in last_update:
                    msg = last_update["message"]
                    self.my_chat_id = msg["chat"]["id"]
                    self.last_message_id = msg["message_id"]
                    self.log(f"📋 My chat ID: {self.my_chat_id}, Last message ID: {self.last_message_id}")
                    return True

        except Exception as e:
            self.log(f"❌ Failed to get chat info: {e}", "ERROR")

        return False

    def load_existing_messages(self):
        """Load existing messages from file to avoid duplicates"""
        if not self.data_file.exists():
            return set(), {}

        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_ids = set(data.get("message_ids", []))
                messages = data.get("messages", {})
                self.log(f"📂 Loaded {len(existing_ids)} existing message IDs from file")
                return existing_ids, messages
        except Exception as e:
            self.log(f"❌ Failed to load existing messages: {e}", "ERROR")
            return set(), {}

    def save_message_data(self, messages_dict, message_ids_set):
        """Save messages to JSON file"""
        try:
            data = {
                "bot_token": self.bot_token.split(":")[0],  # Only save bot ID for security
                "bot_username": self.bot_username,
                "channel_id": self.channel_id,
                "my_chat_id": self.my_chat_id,
                "last_updated": datetime.now().isoformat(),
                "total_messages": len(messages_dict),
                "message_ids": sorted(list(message_ids_set)),
                "messages": messages_dict
            }

            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.log(f"💾 Saved {len(messages_dict)} messages to {self.data_file}")
            return True

        except Exception as e:
            self.log(f"❌ Failed to save messages: {e}", "ERROR")
            return False

    def forward_message(self, from_chat_id, message_id):
        """Forward a single message and return its content"""
        self.handle_rate_limit()

        url = f"{TELEGRAM_API_URL}{self.bot_token}/forwardMessage"
        payload = {
            "from_chat_id": from_chat_id,
            "chat_id": self.my_chat_id,
            "message_id": message_id
        }

        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.post(url, json=payload)
                data = response.json()

                if response.status_code == 200 and data.get("ok"):
                    message = data["result"]
                    self.rate_limit_count = 0  # Reset on success

                    # Extract message content
                    content = {
                        "message_id": message_id,
                        "date": message.get("date"),
                        "text": message.get("text", ""),
                        "caption": message.get("caption", ""),
                        "file_id": None,
                        "media_type": None
                    }

                    # Check for media
                    media_types = ["photo", "document", "video", "audio", "voice", "sticker", "animation"]
                    for media_type in media_types:
                        if media_type in message:
                            content["media_type"] = media_type
                            if isinstance(message[media_type], list):
                                content["file_id"] = message[media_type][-1].get("file_id")
                            else:
                                content["file_id"] = message[media_type].get("file_id")
                            break

                    return content, "success"

                elif response.status_code == 400:
                    return None, "not_found"  # Message doesn't exist

                elif response.status_code == 429:  # Rate limited
                    self.rate_limit_count += 1
                    wait_time = RATE_LIMIT_BURST_DELAY * (attempt + 1)
                    self.log(f"⏳ Rate limited, waiting {wait_time}s (attempt {attempt + 1})", "WARN")
                    time.sleep(wait_time)
                    continue

                else:
                    self.log(f"⚠️ Forward failed for ID {message_id}: {data} (status: {response.status_code})", "WARN")
                    return None, "error"

            except Exception as e:
                self.log(f"❌ Exception forwarding message {message_id} (attempt {attempt + 1}): {e}", "ERROR")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

        return None, "failed"

    def find_message_range(self, channel_id, max_search=1000):
        """Find the actual range of available messages"""
        self.log("🔍 Finding message range...")

        # Try to find the highest message ID
        high = self.last_message_id or 1000
        low = 1

        # Binary search for highest available message
        while low < high:
            mid = (low + high + 1) // 2
            content, status = self.forward_message(channel_id, mid)

            if status == "success":
                low = mid
                self.log(f"✅ Message {mid} exists")
            elif status == "not_found":
                high = mid - 1
                self.log(f"❌ Message {mid} not found")
            else:
                # On error, be conservative
                high = mid - 1

        highest_id = low if low > 0 else 1
        self.log(f"📊 Detected message range: 1 to {highest_id}")
        return 1, highest_id

    async def forward_all_messages(self, skip_existing=True, batch_size=MAX_BATCH_SIZE):
        """Forward all messages from the channel"""
        if not all([self.bot_token, self.my_chat_id]):
            self.log("❌ Bot not properly authenticated", "ERROR")
            return False

        # Load existing messages
        existing_ids, messages_dict = self.load_existing_messages() if skip_existing else (set(), {})

        # Find message range
        start_id, end_id = self.find_message_range(self.channel_id)

        if skip_existing and existing_ids:
            # Filter out existing messages
            all_ids = set(range(start_id, end_id + 1))
            new_ids = sorted(all_ids - existing_ids)
            self.log(f"📋 Found {len(new_ids)} new messages to process (skipping {len(existing_ids)} existing)")
            process_ids = new_ids
        else:
            process_ids = list(range(start_id, end_id + 1))
            self.log(f"📋 Processing {len(process_ids)} messages from {start_id} to {end_id}")

        if not process_ids:
            self.log("✅ No new messages to process")
            return True

        # Process messages in batches
        success_count = 0
        error_count = 0
        not_found_count = 0

        for i in range(0, len(process_ids), batch_size):
            batch = process_ids[i:i + batch_size]
            self.log(f"📦 Processing batch {i//batch_size + 1}: messages {batch[0]} to {batch[-1]}")

            for msg_id in batch:
                content, status = self.forward_message(self.channel_id, msg_id)

                if status == "success" and content:
                    messages_dict[str(msg_id)] = content
                    existing_ids.add(msg_id)
                    success_count += 1
                    if success_count % 50 == 0:  # Log progress every 50 messages
                        self.log(f"📈 Progress: {success_count} messages processed")

                elif status == "not_found":
                    not_found_count += 1

                else:
                    error_count += 1

            # Save progress after each batch
            if messages_dict:
                self.save_message_data(messages_dict, existing_ids)

        # Final save
        if messages_dict:
            self.save_message_data(messages_dict, existing_ids)

        self.log(f"✅ Completed! Success: {success_count}, Not found: {not_found_count}, Errors: {error_count}")
        return True

    async def monitor_new_messages(self, interval=60):
        """Monitor for new messages and forward them"""
        self.log(f"👁️ Starting message monitoring (checking every {interval}s)")

        last_checked_id = self.last_message_id or 1

        while True:
            try:
                # Find current highest message ID
                _, current_highest = self.find_message_range(self.channel_id, max_search=100)

                if current_highest > last_checked_id:
                    new_messages = list(range(last_checked_id + 1, current_highest + 1))
                    self.log(f"🆕 Found {len(new_messages)} new messages: {new_messages[0]} to {new_messages[-1]}")

                    # Load existing data
                    existing_ids, messages_dict = self.load_existing_messages()

                    # Process new messages
                    success_count = 0
                    for msg_id in new_messages:
                        if msg_id not in existing_ids:
                            content, status = self.forward_message(self.channel_id, msg_id)

                            if status == "success" and content:
                                messages_dict[str(msg_id)] = content
                                existing_ids.add(msg_id)
                                success_count += 1

                    if success_count > 0:
                        self.save_message_data(messages_dict, existing_ids)
                        self.log(f"💾 Saved {success_count} new messages")

                    last_checked_id = current_highest

                else:
                    self.log(f"💤 No new messages (last checked: {last_checked_id})")

                await asyncio.sleep(interval)

            except KeyboardInterrupt:
                self.log("⏹️ Monitoring stopped by user")
                break
            except Exception as e:
                self.log(f"❌ Error in monitoring: {e}", "ERROR")
                await asyncio.sleep(interval)

    async def cleanup(self):
        """Clean up resources"""
        if self.client.is_connected():
            await self.client.disconnect()
        self.log("🧹 Cleanup completed")

async def main():
    parser = argparse.ArgumentParser(description="Telegram Bot Message Forwarder")
    parser.add_argument("--bot-token", required=True, help="Telegram bot token")
    parser.add_argument("--channel", required=True, help="Channel/Chat ID to forward from")
    parser.add_argument("--output-dir", default="captured_messages", help="Output directory for messages")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="Skip already processed messages")
    parser.add_argument("--monitor", action="store_true", help="Continue monitoring for new messages")
    parser.add_argument("--monitor-interval", type=int, default=60, help="Monitoring interval in seconds")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")

    args = parser.parse_args()

    forwarder = TelegramForwarder(args.bot_token, args.channel, args.output_dir)

    try:
        # Authenticate
        if not await forwarder.authenticate_bot():
            return 1

        # Get chat info
        if not forwarder.get_my_chat_info():
            forwarder.log("❌ Failed to get chat information", "ERROR")
            return 1

        # Forward all messages
        await forwarder.forward_all_messages(args.skip_existing, args.batch_size)

        # Monitor for new messages if requested
        if args.monitor:
            await forwarder.monitor_new_messages(args.monitor_interval)

    except KeyboardInterrupt:
        forwarder.log("⏹️ Script interrupted by user")
    except Exception as e:
        forwarder.log(f"❌ Unexpected error: {e}", "ERROR")
        return 1
    finally:
        await forwarder.cleanup()

    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
