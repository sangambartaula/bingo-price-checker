import time
import requests
from requests.exceptions import RequestException, HTTPError
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import sys

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

    print("Fetching lowest BIN prices from CoflNet API...")
    
    for item_id, item_tag in item_tags_to_fetch.items():
        market_prices[item_id] = {'lbin_price': 0, 'last_week_lbin': 0, 'last_week_avg': 0, 'last_month_lbin': 0, 'last_month_avg': 0}
        
        try:
            url_active_bin = f"{base_url}/{item_tag}/active/bin"
            response = requests.get(url_active_bin, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if data and isinstance(data, list) and 'startingBid' in data[0]:
                lowest_price = data[0]['startingBid']
                market_prices[item_id]['lbin_price'] = lowest_price / 1_000_000
                print(f"  - Found active BIN for {item_id} (tag: {item_tag}). Price: {format_price(market_prices[item_id]['lbin_price'])} coins")
            else:
                print(f"  - No active BIN auction found for {item_id}. Checking last week's sales...")
                url_sold_week = f"{base_url}/{item_tag}/sold"
                response_week = requests.get(url_sold_week, timeout=5)
                response_week.raise_for_status()
                data_week = response_week.json()
                
                if data_week and isinstance(data_week, list):
                    prices_week = [sale['highestBidAmount'] for sale in data_week if sale.get('bin')]
                    if prices_week:
                        last_week_lbin = min(prices_week) / 1_000_000
                        last_week_avg = (sum(prices_week) / len(prices_week)) / 1_000_000
                        market_prices[item_id]['last_week_lbin'] = last_week_lbin
                        market_prices[item_id]['last_week_avg'] = last_week_avg
                        print(f"    - Found last week's sales. Lowest: {format_price(last_week_lbin)}, Average: {format_price(last_week_avg)}")
                    else:
                        print("    - No BIN sales found in the last week. Checking last month's sales...")
                        url_sold_month = f"{base_url}/{item_tag}/sold?page=last&count=1000"
                        response_month = requests.get(url_sold_month, timeout=5)
                        response_month.raise_for_status()
                        data_month = response_month.json()
                        
                        if data_month and isinstance(data_month, list):
                            prices_month = [sale['highestBidAmount'] for sale in data_month if sale.get('bin')]
                            if prices_month:
                                last_month_lbin = min(prices_month) / 1_000_000
                                last_month_avg = (sum(prices_month) / len(prices_month)) / 1_000_000
                                market_prices[item_id]['last_month_lbin'] = last_month_lbin
                                market_prices[item_id]['last_month_avg'] = last_month_avg
                                print(f"    - Found last month's sales. Lowest: {format_price(last_month_lbin)}, Average: {format_price(last_month_avg)}")
                            else:
                                print("    - No BIN sales found in the last month.")
                        else:
                            print("    - No sales data found for the last month.")
                else:
                    print("    - No sales data found for the last week.")
        except HTTPError as e:
            if e.response.status_code == 400:
                print(f"Error fetching data for {item_id} (tag: {item_tag}): {e.response.status_code} - Bad Request.")
            else:
                print(f"Error fetching data for {item_id}: {e}")
        except RequestException as e:
            print(f"Error fetching data for {item_id}: {e}")

    print("Market data fetched successfully.")
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

    # Dictionary mapping item_id to custom emoji string
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
        emoji = EMOJI_MAPPING.get(item_id, "") # Get emoji, or an empty string if not found
        
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
# Load the token from the .env file
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

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)

results_cache = None
message_cache = None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    print(f"Bot ID: {bot.user.id}")
    await bot.change_presence(activity=discord.Game(name="Bingo Price Checker"))
    print("Ready to check prices!")

@bot.command(name="bingo", help="Checks the profitability of Bingo items and refreshes data.")
async def bingo_command(ctx):
    global results_cache, message_cache

    try:
        await ctx.send("Fetching the latest market data...")
        market_prices = fetch_market_prices()
        
        if not market_prices:
            await ctx.send("Failed to fetch market data. Please try again later.")
            return

        results_cache = calculate_all_results(items_data, market_prices)
        
        # Default sort: coins_per_point, highest to lowest
        initial_embed = get_results_embed(results_cache, sort_key='coins_per_point', reverse=True)
        message_cache = await ctx.send(embed=initial_embed)

        # Add reaction emojis for sorting options
        await message_cache.add_reaction('1️⃣')  # Coins per point (High to Low)
        await message_cache.add_reaction('2️⃣')  # Coins per point (Low to High)
        await message_cache.add_reaction('3️⃣')  # Net profit (High to Low)
        await message_cache.add_reaction('4️⃣')  # Net profit (Low to High)

    except Exception as e:
        print(f"An error occurred in the bingo command: {e}")
        await ctx.send("An unexpected error occurred. Please contact an administrator.")

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot or reaction.message.id != message_cache.id:
        return

    sort_key, reverse_order = 'coins_per_point', True
    
    if reaction.emoji == '1️⃣':
        sort_key, reverse_order = 'coins_per_point', True
    elif reaction.emoji == '2️⃣':
        sort_key, reverse_order = 'coins_per_point', False
    elif reaction.emoji == '3️⃣':
        sort_key, reverse_order = 'net_profit', True
    elif reaction.emoji == '4️⃣':
        sort_key, reverse_order = 'net_profit', False
    else:
        # Ignore other reactions
        return

    new_embed = get_results_embed(results_cache, sort_key=sort_key, reverse=reverse_order)
    await reaction.message.edit(embed=new_embed)
    await reaction.remove(user)

# Run the bot with your token
bot.run(os.getenv("DISCORD_TOKEN"))
