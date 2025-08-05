import time
import requests
from requests.exceptions import RequestException, HTTPError
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import sys
import concurrent.futures

# Load environment variables from .env file
load_dotenv()

# --- Core Logic Functions ---

def format_price(price_in_millions):
    """
    Formats a price in millions into a more readable string with 'M' or 'B'.
    """
    if price_in_millions is None:
        return "N/A"
    
    if price_in_millions >= 1000:
        return f"{price_in_millions / 1000:,.3f}B"
    return f"{price_in_millions:,.2f}M"

def calculate_net_value(item_id, items_data, market_prices, memo):
    if item_id in memo:
        return memo[item_id]

    item = items_data.get(item_id)
    if not item:
        return market_prices.get(item_id, {}).get('lbin_price', 0), 0

    total_points = item.get('points', 0)
    total_cost_in_coins = 0

    prerequisites = item.get('prerequisites', [])
    for prereq in prerequisites:
        prereq_id = prereq['item_id']
        amount = prereq['amount']
        prereq_value = market_prices.get(prereq_id, {}).get('lbin_price', 0)
        total_cost_in_coins += prereq_value * amount

    memo[item_id] = (total_cost_in_coins, total_points)
    return total_cost_in_coins, total_points

def fetch_market_prices():
    market_prices = {}
    base_url = "https://sky.coflnet.com/api/auctions/tag"
    item_tags_to_fetch = {
        "BINGO_TALISMAN": "BINGO_TALISMAN",
        "BINGO_RING": "BINGO_RING",
        "BINGO_ARTIFACT": "BINGO_ARTIFACT",
        "BINGO_RELIC": "BINGO_RELIC",
        "BINGO_DISPLAY": "BINGO_DISPLAY",
        "COLLECTION_DISPLAY": "COLLECTION_DISPLAY",
        "BONZO_STATUE": "BONZO_STATUE",
        "BOOK_OF_STATS": "BOOK_OF_STATS",
        "SPRING_BOOTS": "SPRING_BOOTS",
        "GOLDEN_DANTE_STATUE": "GOLDEN_DANTE_STATUE",
        "DITTO_SKULL": "DITTO_SKULL",
        "DITTO_SKIN": "DITTO_SKIN",
        "BINGO_BLUE_DYE": "DYE_BINGO_BLUE",
    }
    
    print("Fetching lowest BIN prices from CoflNet API concurrently...")
    
    def fetch_item_data(item_id, item_tag):
        price_data = {'lbin_price': 0, 'last_week_lbin': 0, 'last_week_avg': 0, 'last_month_lbin': 0, 'last_month_avg': 0}
        
        try:
            url_active_bin = f"{base_url}/{item_tag}/active/bin"
            response = requests.get(url_active_bin, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if data and isinstance(data, list) and 'startingBid' in data[0]:
                lowest_price = data[0]['startingBid']
                price_data['lbin_price'] = lowest_price / 1_000_000
            else:
                url_sold_week = f"{base_url}/{item_tag}/sold"
                response_week = requests.get(url_sold_week, timeout=5)
                response_week.raise_for_status()
                data_week = response_week.json()
                
                if data_week and isinstance(data_week, list):
                    prices_week = [sale['highestBidAmount'] for sale in data_week if sale.get('bin')]
                    if prices_week:
                        last_week_lbin = min(prices_week) / 1_000_000
                        last_week_avg = (sum(prices_week) / len(prices_week)) / 1_000_000
                        price_data['last_week_lbin'] = last_week_lbin
                        price_data['last_week_avg'] = last_week_avg
                    else:
                        url_sold_month = f"{base_url}/{item_tag}/sold?page=last&count=1000"
                        response_month = requests.get(url_sold_month, timeout=5)
                        response_month.raise_for_status()
                        data_month = response_month.json()
                        
                        if data_month and isinstance(data_month, list):
                            prices_month = [sale['highestBidAmount'] for sale in data_month if sale.get('bin')]
                            if prices_month:
                                last_month_lbin = min(prices_month) / 1_000_000
                                last_month_avg = (sum(prices_month) / len(prices_month)) / 1_000_000
                                price_data['last_month_lbin'] = last_month_lbin
                                price_data['last_month_avg'] = last_month_avg
        except Exception as e:
            print(f"Error fetching data for {item_id}: {e}")
        
        return item_id, price_data

    # Use a thread pool to fetch data for all items concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=13) as executor:
        future_to_item = {
            executor.submit(fetch_item_data, item_id, item_tag): item_id 
            for item_id, item_tag in item_tags_to_fetch.items()
        }
        for future in concurrent.futures.as_completed(future_to_item):
            item_id, price_data = future.result()
            market_prices[item_id] = price_data

    return market_prices


def calculate_all_results(items_data, market_prices):
    results = []
    memo = {}
    for item_id, item_details in items_data.items():
        market_data = market_prices.get(item_id, {})
        market_price = market_data.get('lbin_price', 0)
        total_prereq_cost, total_points = calculate_net_value(item_id, items_data, market_prices, memo)
        direct_points = item_details.get('points', 0)
        net_profit = market_price - total_prereq_cost
        
        coins_per_point = 0
        if direct_points > 0 and net_profit > 0:
            coins_per_point = net_profit / direct_points
        
        results.append({
            'item_id': item_id,
            'market_price': market_price,
            'prereq_cost': total_prereq_cost,
            'net_profit': net_profit,
            'points_spent': direct_points,
            'coins_per_point': coins_per_point,
            'market_data': market_data
        })
    return results

def get_results_embed(results, sort_key='coins_per_point', reverse=True):
    embed = discord.Embed(
        title="Hypixel SkyBlock Bingo Item Value Calculator",
        description=f"Data last updated at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}",
        color=discord.Color.blue()
    )

    EMOJI_MAPPING = {
        "BINGO_DISPLAY": "<:bingodisplay:1402041904346038282>",
        "COLLECTION_DISPLAY": "<:collectiondisplay:1402041894783025262>",
        "BONZO_STATUE": "<:bonzostatue:1402041872591093870>",
        "BOOK_OF_STATS": "<:bookofstats:1402041853079191586>",
        "SPRING_BOOTS": "<:springboots:1402041841573957773>",
        "GOLDEN_DANTE_STATUE": "<:goldendantestatue:1402041832791080960>",
        "DITTO_SKULL": "<:dittoskull:1402041822590664704>",
        "BINGO_TALISMAN": "<:bingotalisman:1402041811597267124>",
        "BINGO_RING": "<:bingoring:1402041801191456898>",
        "BINGO_ARTIFACT": "<:bingoartifact:1402041792135958710>",
        "BINGO_RELIC": "<:bingorelic:1402041782044201040>",
        "BINGO_BLUE_DYE": "<:bingobluedye:1402041767251017831>",
        "DITTO_SKIN": "<:dittoskin:1402041730756509706>"
    }

    sorted_results = sorted(results, key=lambda x: x.get(sort_key, 0), reverse=reverse)

    for item in sorted_results:
        item_id = item['item_id']
        market_price = item['market_price']
        emoji = EMOJI_MAPPING.get(item_id, "")
        
        if item['points_spent'] > 0:
            if market_price > 0:
                if item['net_profit'] > 0:
                    description = (
                        f"**Market Price:** {format_price(item['market_price'])} coins\n"
                        f"**Cost of Prerequisites:** {format_price(item['prereq_cost'])} coins\n"
                        f"**Net Profit:** {format_price(item['net_profit'])} coins\n"
                        f"**Points Spent:** {item['points_spent']} points\n"
                        f"**Coins per point:** {format_price(item['coins_per_point'])}"
                    )
                    embed.add_field(name=f"{emoji} {item_id}", value=description, inline=False)
                else:
                    embed.add_field(name=f"{emoji} {item_id}", value=f"Not Profitable (Net Profit: {format_price(item['net_profit'])})", inline=False)
            else:
                market_data = item['market_data']
                fallback_message = "No Active BIN Auctions Found."
                if market_data.get('last_week_lbin', 0) > 0:
                    fallback_message += (f"\nLast week's lowest BIN was: {format_price(market_data['last_week_lbin'])} coins\n"
                                         f"Last week's average BIN price was: {format_price(market_data['last_week_avg'])} coins")
                elif market_data.get('last_month_lbin', 0) > 0:
                    fallback_message += (f"\nLast month's lowest BIN was: {format_price(market_data['last_month_lbin'])} coins\n"
                                         f"Last month's average BIN price was: {format_price(market_data['last_month_avg'])} coins")
                embed.add_field(name=f"{emoji} {item_id}", value=fallback_message, inline=False)
    
    embed.set_footer(text="Data sourced from SkyCofl's API: https://sky.coflnet.com/api")
    return embed

# --- Discord Bot Setup ---
try:
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if DISCORD_TOKEN is None:
        raise ValueError("DISCORD_TOKEN not found in .env file")
except ValueError as e:
    print(f"Error: {e}")
    sys.exit(1)


# Define the items and their costs as provided by the user.
items_data = {
    "BINGO_DISPLAY": {"points": 50, "prerequisites": []},
    "COLLECTION_DISPLAY": {"points": 30, "prerequisites": []},
    "BONZO_STATUE": {"points": 30, "prerequisites": []},
    "BOOK_OF_STATS": {"points": 5, "prerequisites": []},
    "SPRING_BOOTS": {"points": 150, "prerequisites": []},
    "GOLDEN_DANTE_STATUE": {"points": 100, "prerequisites": []},
    "DITTO_SKULL": {"points": 50, "prerequisites": []},
    "BINGO_TALISMAN": {"points": 100, "prerequisites": []},
    "BINGO_RING": {"points": 150, "prerequisites": [{"item_id": "BINGO_TALISMAN", "amount": 1}]},
    "BINGO_ARTIFACT": {"points": 150, "prerequisites": [{"item_id": "BINGO_RING", "amount": 1}]},
    "BINGO_RELIC": {"points": 200, "prerequisites": [{"item_id": "BINGO_ARTIFACT", "amount": 1}]},
    "BINGO_BLUE_DYE": {"points": 500, "prerequisites": []},
    "DITTO_SKIN": {"points": 100, "prerequisites": []}
}

# Define the view and dropdown for sorting
class SortView(discord.ui.View):
    def __init__(self, bot_instance, results, original_author):
        super().__init__()
        self.bot_instance = bot_instance
        self.results = results
        self.original_author = original_author
        
        self.add_item(SortDropdown(self.results))
    
    # This prevents anyone other than the original user from using the dropdown
    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user == self.original_author

class SortDropdown(discord.ui.Select):
    def __init__(self, results):
        self.results = results
        options = [
            discord.SelectOption(label="Coins per Point (Highest to Lowest)", value="coins_per_point_desc"),
            discord.SelectOption(label="Coins per Point (Lowest to Highest)", value="coins_per_point_asc"),
            discord.SelectOption(label="Net Profit (Highest to Lowest)", value="net_profit_desc"),
            discord.SelectOption(label="Net Profit (Lowest to Highest)", value="net_profit_asc")
        ]
        super().__init__(placeholder="Choose a sorting option...", options=options)

    async def callback(self, interaction: discord.Interaction):
        sort_key, reverse_order = 'coins_per_point', True
        
        if self.values[0] == "coins_per_point_desc":
            sort_key, reverse_order = 'coins_per_point', True
        elif self.values[0] == "coins_per_point_asc":
            sort_key, reverse_order = 'coins_per_point', False
        elif self.values[0] == "net_profit_desc":
            sort_key, reverse_order = 'net_profit', True
        elif self.values[0] == "net_profit_asc":
            sort_key, reverse_order = 'net_profit', False

        new_embed = get_results_embed(self.results, sort_key=sort_key, reverse=reverse_order)
        await interaction.response.edit_message(embed=new_embed)


intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)

results_cache = None

async def bingo_logic(ctx_or_interaction, is_slash_command=False):
    global results_cache

    try:
        # Acknowledge slash command to prevent timeout
        if is_slash_command:
            await ctx_or_interaction.response.defer()
            send_func = ctx_or_interaction.followup.send
        else:
            send_func = ctx_or_interaction.send
            await send_func("Fetching the latest market data...")

        market_prices = fetch_market_prices()
        
        if not market_prices:
            await send_func("Failed to fetch market data. Please try again later.")
            return

        results_cache = calculate_all_results(items_data, market_prices)
        
        initial_embed = get_results_embed(results_cache, sort_key='coins_per_point', reverse=True)
        view = SortView(bot, results_cache, ctx_or_interaction.user if is_slash_command else ctx_or_interaction.author)
        await send_func(embed=initial_embed, view=view)

    except Exception as e:
        print(f"An error occurred in the bingo command: {e}")
        await send_func("An unexpected error occurred. Please contact an administrator.")


@bot.command(name="bingo", help="Checks the profitability of Bingo items and refreshes data.")
async def bingo_command(ctx):
    await bingo_logic(ctx, is_slash_command=False)


@bot.tree.command(name="bingo", description="Checks the profitability of Bingo items and refreshes data.")
async def bingo_slash_command(interaction: discord.Interaction):
    await bingo_logic(interaction, is_slash_command=True)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    print(f"Bot ID: {bot.user.id}")
    await bot.change_presence(activity=discord.Game(name="Bingo Price Checker"))
    print("Ready to check prices!")
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

# Run the bot with token
bot.run(os.getenv("DISCORD_TOKEN"))