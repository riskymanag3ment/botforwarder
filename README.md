# botforwarder

# Telegram Bot Message Forwarder

A command-line tool for forwarding messages from Telegram channels/chats through bot APIs. This tool enables researchers and security professionals to analyze Telegram bot communications and message patterns.

## Disclaimer

**This tool is intended for educational and research purposes only.** It should only be used on systems and channels that you own or have explicit permission to analyze. The authors are not responsible for any misuse of this software.

This project is loosely based upon the concepts from [matkap](https://github.com/0x6rss/matkap) but has been rewritten as a command-line interface with additional features for research workflows.

## Features

- **Command-line interface** for automated workflows
- **Automatic session management** - authenticate once, reuse sessions
- **Rate limiting protection** with exponential backoff
- **Batch processing** for large message volumes
- **JSON output format** for structured data analysis
- **Progress monitoring** and comprehensive logging
- **Duplicate detection** to skip already processed messages
- **Real-time monitoring** mode for ongoing analysis
- **OTP authentication** with automatic session saving

## Installation

1. Clone the repository:
```bash
git clone https://github.com/riskymanag3ment/botforwarder
cd botforwarder
```

2. Install dependencies:
```bash
pip install telethon requests python-dotenv
```

3. Set up your environment variables in a `.env` file:
```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=your_phone_number
```

> **Note:** Get your API credentials from [my.telegram.org](https://my.telegram.org)

## Usage

### Basic Message Forwarding

```bash
python botforwarder.py --bot-token "123456789:AABBccDDee..." --channel "-1001234567890"
```

### Skip Already Processed Messages

```bash
python botforwarder.py --bot-token "123456789:AABBccDDee..." --channel "@channelname" --skip-existing
```

### Monitor for New Messages

```bash
python botforwarder.py --bot-token "123456789:AABBccDDee..." --channel "123456789" --monitor --monitor-interval 30
```

### Custom Output Directory

```bash
python botforwarder.py --bot-token "123456789:AABBccDDee..." --channel "-1001234567890" --output-dir "./analysis_data"
```

### Batch Processing

```bash
python botforwarder.py --bot-token "123456789:AABBccDDee..." --channel "-1001234567890" --batch-size 50
```

## Command Line Arguments

| Argument | Required | Description | Default |
|----------|----------|-------------|---------|
| `--bot-token` | ✅ | Telegram bot token | - |
| `--channel` | ✅ | Channel/Chat ID to forward from | - |
| `--output-dir` | ❌ | Output directory for messages | `captured_messages` |
| `--skip-existing` | ❌ | Skip already processed messages | `True` |
| `--monitor` | ❌ | Continue monitoring for new messages | `False` |
| `--monitor-interval` | ❌ | Monitoring interval in seconds | `60` |
| `--batch-size` | ❌ | Batch size for processing | `100` |

## Output Structure

The tool creates organized output files:

```
captured_messages/
├── bot_123456_channel_-1001234567890_messages.json  # Message data
├── bot_123456_channel_-1001234567890_log.txt        # Processing logs
└── telegram_session_123456.txt                      # Saved session
```

### JSON Output Format

```json
{
  "bot_token": "123456",
  "bot_username": "research_bot",
  "channel_id": "-1001234567890",
  "total_messages": 1250,
  "messages": {
    "1": {
      "message_id": 1,
      "date": 1693123456,
      "text": "Message content...",
      "media_type": "photo",
      "file_id": "BAACAgIAAxkDAAIC..."
    }
  }
}
```

## How It Works

1. **Authentication**: Connects to Telegram using your account credentials
2. **Bot Validation**: Verifies the provided bot token is valid
3. **Session Management**: Automatically saves/loads session strings
4. **Message Discovery**: Finds available message range using binary search
5. **Batch Processing**: Forwards messages in configurable batches
6. **Rate Limiting**: Automatically handles Telegram's API limits
7. **Data Storage**: Saves messages in structured JSON format

## Security Considerations

- **Session Storage**: Sessions are stored locally - keep them secure
- **Bot Tokens**: Never commit bot tokens to version control
- **Rate Limits**: Tool respects Telegram's rate limiting
- **Permission**: Only use on channels/bots you own or have permission to analyze

## Troubleshooting

### Common Issues

**"Missing Telegram credentials"**
- Ensure your `.env` file has all required variables
- Get API credentials from [my.telegram.org](https://my.telegram.org)

**"Rate limited"**
- The tool handles this automatically with backoff
- Consider reducing batch size with `--batch-size`

**"Authentication failed"**
- Delete the session file to force re-authentication
- Check your phone number format (+1234567890)

**"No messages found"**
- Verify the channel ID is correct
- Ensure the bot has been added to the channel
- Check that `/start` was sent to the bot

## Research Applications

This tool is designed for legitimate research purposes including:

- **Bot Behavior Analysis**: Understanding how malicious bots operate
- **Communication Pattern Research**: Analyzing message flows and timing
- **Threat Intelligence**: Gathering data on suspicious channels
- **Security Research**: Investigating bot-based attack vectors

## Contributing

Contributions are welcome! Please ensure any additions maintain the educational focus and include appropriate safety considerations.

## License

This project is released under the MIT License. See `LICENSE` file for details.

## Acknowledgments

- Loosely based upon concepts from [matkap](https://github.com/0x6rss/matkap) by 0x6rss
- Built with [Telethon](https://github.com/LonamiWebs/Telethon) for Telegram integration
- Designed for security research and educational purposes

---

**Remember: Use responsibly and only on systems you own or have explicit permission to test.**
