### Bingo Price Checker
Will show best bingo items to buy with your points in Hypixel Skyblock. Coins/point and Coins overall.

This is a Discord bot designed to help players of Hypixel SkyBlock determine the most profitable items to purchase with their Bingo points. It fetches real-time market data to calculate key metrics and presents them in a clear, easy-to-read format.

### Features
Real-time Price Fetching: Gathers the latest market data for a list of Bingo-related items by calling the SkyCofl API.

Profitability Metrics: Calculates the net profit and "coins per point" for each item, accounting for the cost of any prerequisite items.

Slash and Prefix Commands: Supports both the legacy !bingo prefix command and the modern /bingo slash command.

Interactive Sorting: Provides an interactive drop-down menu to sort results by different criteria, such as net profit or coins per point.

Fallback Data: Displays historical price data (from the last week or month) if no active auctions are found for a specific item.

### Getting Started
Follow these steps to set up and run the bot locally.

### Prerequisites

  * Python 3.9 or higher
  * Git

### Setup Instructions

1.  **Set up your Discord Application:**

      * Go to the [Discord Developer Portal](https://discord.com/developers/applications).
      * Create a new application and name your bot.
      * In the **Bot** tab, generate a bot token. **Keep this token safe and private.**
      * In the **OAuth2** \> **URL Generator** section, select the `bot` and `applications.commands` scopes.
      * Choose the necessary permissions for your bot (e.g., `Read Message History`, `Send Messages`).
      * Copy the generated URL and use it to invite the bot to your server.

2.  **Clone the repository:**

    ```bash
    git clone https://github.com/sangambartaula/bingo-price-checker.git
    cd bingo-price-checker
    ```

3.  **Create and activate a virtual environment:**

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

4.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

5.  **Set your Discord bot token:**
    Create a `.env` file in the project's root directory and add your bot's token. The `.gitignore` file ensures this token will not be committed to your repository.

    ```
    DISCORD_TOKEN="YOUR_BOT_TOKEN_HERE"
    ```

### Running the Bot

To start the bot, run the `bingo.py` file with the correct Python interpreter:

```bash
python3 bingo.py
```
