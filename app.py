
import matplotlib
matplotlib.use('Agg')  # Force a non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import seaborn as sns
import io
import os
import numpy as np
import base64
from dash import Dash, html, dcc
from dash import Input, Output, dash_table
# --- DATA PROCESSING 
bids = pd.read_csv("files/bids.csv")
forecast = pd.read_csv("files/spot_forecast.csv")

bids["Volume"] = round(bids["Volume"],2)
forecast["SpotForecast"]=round(forecast["SpotForecast"],2)

# bids_long for initial plot
bids_long_raw = bids[bids["Volume"] > 0]

# Outlier filtering logic (From your notebook)
Q1 = bids_long_raw['Price'].quantile(0.25)
Q3 = bids_long_raw['Price'].quantile(0.75)
IQR = Q3 - Q1
lower_bound = Q1 - 1.5 * IQR
upper_bound = Q3 + 1.5 * IQR
bids_long_clean = bids_long_raw[(bids_long_raw['Price'] >= lower_bound) & (bids_long_raw['Price'] <= upper_bound)]

bids_short = bids[bids["Volume"]<0]
Q1 = bids_short['Price'].quantile(0.25)
Q3 = bids_short['Price'].quantile(0.75)
IQR = Q3 - Q1

lower_bound = Q1 - 1.5 * IQR
upper_bound = Q3 + 1.5 * IQR

bids_short = bids_short[(bids_short['Price'] >= lower_bound) & (bids_short['Price'] <= upper_bound)]

short_volume = round(bids_short["Volume"].sum(),0)
long_volume = round(bids_long_clean["Volume"].sum(),0)

bids_fixed = pd.concat([bids_long_clean, bids_short], axis=0)
bids_fixed["operation"] = np.where(bids_fixed["Volume"]<0, "sell", "buy")

# Code for internal correction
new_buys = pd.DataFrame()
new_sells = pd.DataFrame()

for hour in range(0,24):
    df_buys = bids_fixed[(bids_fixed["Hour"]==hour) & (bids_fixed["operation"]=="buy")]
    df_sells = bids_fixed[(bids_fixed["Hour"]==hour)& (bids_fixed["operation"]=="sell")]

    df_buys = df_buys.sort_values('Price', ascending=True).reset_index(drop=True)
    df_sells = df_sells.sort_values('Price', ascending=True).reset_index(drop=True)

    tolerance = 2
    i = 0  

    while i < len(df_buys) and not df_sells.empty:
        buy_row = df_buys.iloc[i]
        buy_price = buy_row['Price']
        
        # Calculate absolute price difference for all remaining sell orders
        df_sells['diff'] = (df_sells['Price'] - buy_price).abs()
        
        # Find the row index of the closest sell order
        closest_idx = df_sells['diff'].idxmin()
        min_diff = df_sells.loc[closest_idx, 'diff']
        
        # Check if the closest match is within the tolerance of 2
        if min_diff <= tolerance:
            buy_vol = df_buys.loc[i, 'Volume']
            sell_vol = df_sells.loc[closest_idx, 'Volume']
            
            # Scenario A: Buy volume is higher
            if buy_vol > abs(sell_vol):
                df_buys.loc[i, 'Volume'] += sell_vol # Subtract sell volume
                df_sells = df_sells.drop(closest_idx).reset_index(drop=True)
                # We don't increment 'i' because the current buy still has volume left
                
            # Scenario B: Sell volume is higher
            elif abs(sell_vol) > buy_vol:
                df_sells.loc[closest_idx, 'Volume'] += buy_vol # Reduce sell volume
                df_buys = df_buys.drop(i).reset_index(drop=True)
                # We don't increment 'i' because a new row has moved into the current index
                
            # Scenario C: Volumes are equal
            else:
                df_buys = df_buys.drop(i).reset_index(drop=True)
                df_sells = df_sells.drop(closest_idx).reset_index(drop=True)
                # Both rows gone; new rows shift into the current indices
        else:
            # If the closest sell is outside the tolerance, move to the next buy
            i += 1

    # Clean up the helper column
    if not df_sells.empty:
        df_sells = df_sells.drop(columns=['diff'])
    new_buys = pd.concat([new_buys, df_buys], ignore_index=True)
    new_sells = pd.concat([new_sells, df_sells], ignore_index=True)
    
final_buy_strategy = pd.read_csv("files/final_buy_strategy.csv")    
new_bids_post = pd.concat([new_buys, new_sells], axis=0)
new_bids_post["Volume"].sum()

new_buys2 = pd.DataFrame()
new_sells2 = pd.DataFrame()

for hour in range(0,24):
    df_buys = new_buys[(new_buys["Hour"]==hour) ]
    df_sells = new_sells[(new_sells["Hour"]==hour)]
    
    df_buys = df_buys.sort_values('Price', ascending=False).reset_index(drop=True)
    df_sells = df_sells.sort_values('Price', ascending=True).reset_index(drop=True)

    spread = 2

    # 2. Iterative Matching Process
    # We continue as long as both sides have orders AND the price condition is met
    while not df_buys.empty and not df_sells.empty:
        
        max_buy_price = df_buys.loc[0, 'Price']
        min_sell_price = df_sells.loc[0, 'Price']
        
        # Check your condition: Max Buy < Min Sell + 5
        if max_buy_price < (min_sell_price - spread):
            #print(f("the max buy price is {max_buy_price}"))
            #print(f("the min sell price is {min_sell_price}"))
            break  # Gap is too large, no more trades possible
        
        # Get volumes (Remember: Sell volume is negative)
        buy_vol = df_buys.loc[0, 'Volume']
        sell_vol = df_sells.loc[0, 'Volume'] 
        
        # Calculate the absolute difference to see which is "bigger"
        # We use abs() because sell_vol is negative
        if buy_vol > abs(sell_vol):
            # Buy is larger: Update Buy volume and remove the Sell row
            df_buys.loc[0, 'Volume'] += sell_vol 
            df_sells = df_sells.drop(0).reset_index(drop=True)
            
        elif abs(sell_vol) > buy_vol:
            # Sell is larger: Update Sell volume and remove the Buy row
            df_sells.loc[0, 'Volume'] += buy_vol
            df_buys = df_buys.drop(0).reset_index(drop=True)
            
        else:
            # Perfect match: Both are equal, remove both
            df_buys = df_buys.drop(0).reset_index(drop=True)
            df_sells = df_sells.drop(0).reset_index(drop=True)
    new_buys2 = pd.concat([new_buys2, df_buys], ignore_index=True)
    new_sells2 = pd.concat([new_sells2, df_sells], ignore_index=True)
    new_bids_post2 = pd.concat([new_buys2, new_sells2], axis=0)
    
    #new_bids_post2["Volume"].sum()
# FORECAST

factor = 0.1
forecast["yhat_lower"] = round(forecast["SpotForecast"]*(1-factor),2)
forecast["yhat_upper"] = round(forecast["SpotForecast"]*(1+factor),2)
bids_forecast = pd.merge(new_bids_post2, forecast, on='Hour', how='left')
bids_forecast["on_range"] = np.where((bids_forecast["Price"]>bids_forecast["yhat_lower"])&(bids_forecast["Price"]<bids_forecast["yhat_upper"]),1,0)

bids_forecast['distance']= round(abs(bids_forecast['Price']-bids_forecast['SpotForecast']),2)

# TEMPORAL - EXAMPLE
bids_forecast_temp2 = bids_forecast[(bids_forecast["Hour"]==1)&(bids_forecast["operation"]=="buy")]
total_volume = abs(bids_forecast_temp2["Volume"].sum())
bids_forecast_temp2["weight"]=round(bids_forecast_temp2["Volume"]/total_volume,3)
bids_forecast_temp2['distance_weighted'] = round((bids_forecast_temp2["weight"]/bids_forecast_temp2["distance"])+bids_forecast_temp2["on_range"],2)
bids_forecast_temp2["Volume"] = round(bids_forecast_temp2["Volume"],0)
bids_sell_forecast_final = pd.DataFrame()
for i in range(0,24):
    
    bids_sell_forecast_temp = bids_forecast[(bids_forecast["Hour"]==i)&(bids_forecast["operation"]=="sell")]

    total_volume = abs(bids_sell_forecast_temp["Volume"].sum())

    bids_sell_forecast_temp["weight"]=bids_sell_forecast_temp["Volume"]/-total_volume
    
    bids_sell_forecast_temp['distance_weighted'] = (bids_sell_forecast_temp["weight"]/bids_sell_forecast_temp["distance"])+bids_sell_forecast_temp["on_range"]

    max_dist_weight = bids_sell_forecast_temp["distance_weighted"].max()

    temp_row = bids_sell_forecast_temp[bids_sell_forecast_temp["distance_weighted"]==max_dist_weight]

    temp_row["Volume"]=total_volume
    bids_sell_forecast_final = pd.concat([bids_sell_forecast_final, temp_row], ignore_index=True)
                                         
bids_buy_forecast_final = pd.DataFrame()
for i in range(0,24):
    
    bids_forecast_temp = bids_forecast[(bids_forecast["Hour"]==i)&(bids_forecast["operation"]=="buy")]

    total_volume = abs(bids_forecast_temp["Volume"].sum())

    bids_forecast_temp["weight"]=bids_forecast_temp["Volume"]/total_volume
    bids_forecast_temp['distance_weighted'] = (bids_forecast_temp["weight"]/bids_forecast_temp["distance"])+bids_forecast_temp["on_range"]

    max_dist_weight = bids_forecast_temp["distance_weighted"].max()

    temp_row = bids_forecast_temp[bids_forecast_temp["distance_weighted"]==max_dist_weight]

    temp_row["Volume"]=total_volume
    bids_buy_forecast_final = pd.concat([bids_buy_forecast_final, temp_row], ignore_index=True)
    
bids_sell_forecast_final = bids_sell_forecast_final.sort_values("Price")
bids_sell_forecast_final['Price_Diff'] = bids_sell_forecast_final['Price'].diff()

bids_sell_forecast_final['Price_Diff'] = abs(bids_sell_forecast_final['Price_Diff'] )
temp1 = bids_buy_forecast_final[bids_buy_forecast_final["Hour"]==1]

bids_buy_forecast_final = bids_buy_forecast_final.sort_values("Price")
bids_buy_forecast_final['Price_Diff'] = bids_buy_forecast_final['Price'].diff()

bids_buy_forecast_final_temp = bids_buy_forecast_final[["Price","SpotForecast","on_range","distance","Price_Diff"]]
bids_buy_forecast_final_temp["Price_Diff"] = round(bids_buy_forecast_final_temp["Price_Diff"],2)


current_val = 2
target = 100
step = 0.1

while target > 20:
 
    condition = bids_sell_forecast_final['Price_Diff'] > current_val
    condition2 = bids_buy_forecast_final['Price_Diff'] > current_val

    bids_sell_forecast_final['block'] = condition.cumsum() + 1
    bids_buy_forecast_final['block'] = condition2.cumsum() + 1
    
    target = max(bids_buy_forecast_final['block'])+max(bids_sell_forecast_final['block'])
    current_val = round(current_val + step, 1)

#for buying
block_distance = bids_buy_forecast_final.groupby("block")["distance"].min()
block_distance2 = pd.merge(block_distance, bids_buy_forecast_final[["Price", "block", "distance"]], on = ("block", "distance"), how = 'left')
block_distance2 = block_distance2.rename(columns={"Price":"Block_price"})
bids_buy_forecast_final2 = pd.merge(bids_buy_forecast_final, block_distance2[["Block_price", "block"]], on = ("block"), how = 'left')
bids_buy_forecast_final2["Price"] = bids_buy_forecast_final2["Block_price"]

#for selling
block_distance = bids_sell_forecast_final.groupby("block")["distance"].min()
block_distance2 = pd.merge(block_distance, bids_sell_forecast_final[["Price", "block", "distance"]], on = ("block", "distance"), how = 'left')
block_distance2 = block_distance2.rename(columns={"Price":"Block_price"})
bids_sell_forecast_final = pd.merge(bids_sell_forecast_final, block_distance2[["Block_price", "block"]], on = ("block"), how = 'left')
bids_sell_forecast_final["Price"] = bids_sell_forecast_final["Block_price"]

final_df = pd.concat([bids_sell_forecast_final, bids_buy_forecast_final2], ignore_index=True)
temp2 = final_df      

bids_buy_forecast_final2_temp = bids_buy_forecast_final2[["Price","SpotForecast","on_range","distance","Price_Diff", "block"]]     
bids_buy_forecast_final2_temp["Price_Diff"] = round(bids_buy_forecast_final2_temp["Price_Diff"],2)

# --- PLOT GENERATION FUNCTIONS ---
def generate_seaborn_plot(df, title):
    plt.figure(figsize=(12, 6))
    sns.set_theme(style="whitegrid")
    sns.boxplot(data=df, x='Hour', y='Price')
    plt.title(title)
    plt.xlabel('Hour of the Day')
    plt.ylabel('Price ($)')
    
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight')
    plt.close()
    data = base64.b64encode(buf.getbuffer()).decode("utf8")
    return f"data:image/png;base64,{data}"

# --- Generate the Final Scatterplot ---
plt.figure(figsize=(12, 6))
sns.set_theme(style="whitegrid")
sns.scatterplot(
    data=new_bids_post2, 
    x='Hour', 
    y='Price', 
    hue='operation',
    alpha=0.7
)
plt.title('Final Price Distribution by Hour')
plt.xlabel('Hour of the Day')
plt.ylabel('Price ($)')

# Save to buffer
buf = io.BytesIO()
plt.savefig(buf, format="png", bbox_inches='tight')
plt.close()
final_scatter_img = f"data:image/png;base64,{base64.b64encode(buf.getbuffer()).decode('utf8')}"

# --- Generate the Forecast Plot ---
plt.figure(figsize=(12, 6))
sns.set_theme(style="whitegrid")

# Main Forecast Line
sns.lineplot(data=forecast, x='Hour', y='SpotForecast', color='#2ca02c', label='Spot Forecast')

# Upper and Lower Bounds (Uncertainty)
sns.lineplot(data=forecast, x='Hour', y='yhat_upper', color='gray', linestyle='--', label='Upper Bound', alpha=0.5)
sns.lineplot(data=forecast, x='Hour', y='yhat_lower', color='gray', linestyle='--', label='Lower Bound', alpha=0.5)

# Optional: Fill the area between bounds for better visibility
plt.fill_between(forecast['Hour'], forecast['yhat_lower'], forecast['yhat_upper'], color='gray', alpha=0.1)

plt.title('Spot Price Forecast by Hour')
plt.xlabel('Hour of the Day')
plt.ylabel('Price ($)')
plt.legend()

# Save to buffer
buf = io.BytesIO()
plt.savefig(buf, format="png", bbox_inches='tight')
plt.close()
forecast_img = f"data:image/png;base64,{base64.b64encode(buf.getbuffer()).decode('utf8')}"

# --- Generate the Bids vs Forecast Plot ---
plt.figure(figsize=(12, 6))
sns.set_theme(style="whitegrid")

# Layer 1: The Bids (Points)
sns.scatterplot(
    data=bids_forecast, 
    x='Hour', 
    y='Price', 
    hue='operation',
    alpha=0.5,
    palette={'buy': '#1f77b4', 'sell': '#ff7f0e'} # Blue for buy, Orange for sell
)

# Layer 2: The Forecast (Line)
sns.lineplot(
    data=bids_forecast, 
    x='Hour', 
    y='SpotForecast', 
    color='red', 
    linewidth=3, 
    label='Spot Forecast',
    marker='o'
)

plt.title('Price Distribution by Hour (With Forecast)')
plt.xlabel('Hour of the Day')
plt.ylabel('Price ($)')
plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left') # Move legend outside to avoid overlap

# Save to buffer
buf = io.BytesIO()
plt.savefig(buf, format="png", bbox_inches='tight')
plt.close()
bids_forecast_img = f"data:image/png;base64,{base64.b64encode(buf.getbuffer()).decode('utf8')}"

# --- Generate the Final Sell Strategy Plot ---
plt.figure(figsize=(12, 6))
sns.set_theme(style="whitegrid")

# Layer 1: The Bids scaled by Volume
sns.scatterplot(
    data=bids_sell_forecast_final, 
    x='Hour', 
    y='Price', 
    hue='operation',
    size='Volume',     # Mapping point size to MW volume
    sizes=(40, 400),   # Adjusts the range of the bubble sizes
    alpha=0.6,
    palette={'sell': '#ff7f0e', 'buy': '#1f77b4'} 
)

# Layer 2: The Forecast line
sns.lineplot(
    data=bids_sell_forecast_final, 
    x='Hour', 
    y='SpotForecast', 
    color='red', 
    linewidth=3, 
    label='Spot Forecast',
    marker='o'
)

plt.title('Final Sell Price Distribution (Point Size = Volume)')
plt.xlabel('Hour of the Day')
plt.ylabel('Price ($)')
plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

# Buffer and Base64 encoding
buf = io.BytesIO()
plt.savefig(buf, format="png", bbox_inches='tight')
plt.close()
final_sell_plot_img = f"data:image/png;base64,{base64.b64encode(buf.getbuffer()).decode('utf8')}"

# --- Generate the Final Buy Strategy Plot ---
plt.figure(figsize=(12, 6))
sns.set_theme(style="whitegrid")

# Layer 1: Scatter with size representing Volume
sns.scatterplot(
    data=bids_buy_forecast_final, 
    x='Hour', 
    y='Price', 
    hue='operation',
    size='Volume',     # Mapping point size to MW volume
    sizes=(40, 400),   
    alpha=0.6,
    palette={'buy': '#1f77b4'} 
)

# Layer 2: Forecast line
sns.lineplot(
    data=bids_buy_forecast_final, 
    x='Hour', 
    y='SpotForecast', 
    color='red', 
    linewidth=3, 
    label='Spot Forecast',
    marker='o'
)

plt.title('Final Buy Price Distribution (Point Size = Volume)')
plt.xlabel('Hour of the Day')
plt.ylabel('Price ($)')
plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

buf = io.BytesIO()
plt.savefig(buf, format="png", bbox_inches='tight')
plt.close()
final_buy_plot_img = f"data:image/png;base64,{base64.b64encode(buf.getbuffer()).decode('utf8')}"


# --- Generate the Final Buy Strategy Plot ---
plt.figure(figsize=(12, 6))
sns.set_theme(style="whitegrid")

# Layer 1: Scatter plot for buy operations
sns.scatterplot(
    data=final_buy_strategy, 
    x='Hour', 
    y='Price', 
    hue='operation',
    # size='Volume', # Uncomment if you want to scale bubbles by MW
    alpha=0.7,
    palette={'buy': '#1f77b4', 'sell': '#ff7f0e'} 
)

# Layer 2: Forecast line
sns.lineplot(
    data=final_buy_strategy, 
    x='Hour', 
    y='SpotForecast', 
    color='red', 
    linewidth=3, 
    label='Spot Forecast',
    marker='o'
)

plt.title('Final Buy Strategy Distribution (vs. Forecast)')
plt.xlabel('Hour of the Day')
plt.ylabel('Price ($)')
plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

# Buffer and Base64 encoding
buf = io.BytesIO()
plt.savefig(buf, format="png", bbox_inches='tight')
plt.close()
final_buy_strategy_img = f"data:image/png;base64,{base64.b64encode(buf.getbuffer()).decode('utf8')}"
# --- DASH APP LAYOUT ---
app = Dash(__name__)
@app.callback(
    Output('strip-plot', 'src'),
    Input('hour-slider', 'value')
)
def update_plot(selected_hour):
    filtered_df = bids_fixed[bids_fixed["Hour"] == selected_hour]
    
    if filtered_df.empty:
        return "" # Prevents crash if no data

    fig, ax = plt.subplots(figsize=(10, 6)) # Thread-safe subplots
    sns.stripplot(data=filtered_df, x='operation', y='Price', jitter=True, alpha=0.6, ax=ax)
    ax.set_title(f'Price Distribution by Operation - Hour {selected_hour}')
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig) 
    data = base64.b64encode(buf.getbuffer()).decode("utf8")
    return f"data:image/png;base64,{data}"

@app.callback(
    Output('strip-plot-post', 'src'),
    Input('hour-slider', 'value')
)
def update_plot_post(selected_hour):
    filtered_df = new_bids_post[new_bids_post["Hour"] == selected_hour]
    
    if filtered_df.empty:
        return ""

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.stripplot(data=filtered_df, x='operation', y='Price', jitter=True, alpha=0.6, ax=ax)
    ax.set_title(f'Post-Correction: Price Distribution - Hour {selected_hour}')
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    data = base64.b64encode(buf.getbuffer()).decode("utf8")
    return f"data:image/png;base64,{data}"

@app.callback(
    Output('strip-plot_v3', 'src'),
    Input('hour-slider', 'value')
)
def update_plot_post2(selected_hour):
    filtered_df = new_bids_post2[new_bids_post2["Hour"] == selected_hour]
    
    if filtered_df.empty:
        return ""

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.stripplot(data=filtered_df, x='operation', y='Price', jitter=True, alpha=0.6, ax=ax)
    ax.set_title(f'Post-Correction 2: Price Distribution - Hour {selected_hour}')
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    data = base64.b64encode(buf.getbuffer()).decode("utf8")
    return f"data:image/png;base64,{data}"


app.layout = html.Div(style={'fontFamily': 'sans-serif', 'padding': '40px', 'maxWidth': '1000px', 'margin': 'auto'}, children=[
    
    # Notebook Cell 1: Header
    dcc.Markdown("# Trding Bid Optimization"),
    

    
    # Notebook Cell 5: Second Plot (Cleaned)
    html.Img(src=generate_seaborn_plot(bids_long_clean, 'Price Distribution by Hour (Cleaned)'), 
             style={'width': '100%', 'marginBottom': '30px'}),
    
    dcc.Markdown(f"We check on the initial volume from both operations: Shorts: **{short_volume}** units and Longs: **{long_volume}**"),
    
    dcc.Markdown("""
    ## Internal Correction
    
    In this fase we pair the buy orders with similar price to sell orders. For Example buying 50 MW at $40 and selling 50MW at $40.  
    
    As we can observe there are many sell and buy options with siilar prices.
    """),
    

    html.H3("Select Hour for Price Distribution:"),
    dcc.Slider(
        id='hour-slider',
        min=0, max=23, step=1, value=1,
        marks={i: str(i) for i in range(0, 24)}
    ),
    html.Div([
        html.Img(id='strip-plot', style={'width': '80%'})
    ], style={'textAlign': 'center'}),
    
    dcc.Markdown("""
    ### Algorith to pair buy and sell positions with same price
    
    To solve this situation, an algorithm is implement to match the Buys and the Sells:
    1. Initialization and Sorting: The process begins by targeting the lowest-priced buy orders first. This "bottom-up" approach ensures that the most competitive buy prices are settled first.

    2. Price Proximity: For every buy order, the algorithm searches the available sell orders to find the absolute closest price match. 

    Constraint Rule: The match is only valid if the price difference is within a specific tolerance of 2 units on the price, the buy order remains unmatched and the algorithm moves to the next row.

    3. Volume Settlement (The "Netting" Phase)Once a price match is confirmed, the algorithm compares the Volumes to determine how to "settle" or "net" the rows.
    """),

    html.Div([
        html.Img(id='strip-plot-post', style={'width': '80%'}) # New ID
    ], style={'textAlign': 'center'}),
    
    dcc.Markdown("""
    ### Liquidity Matching Algorithm
    
    The process tries to "net out" (cancel out) buy and sell orders. It keeps running as long as the highest buy price is close enough to the lowest sell price (within a margin of 5).

    How it works: 

    Step A: It picks two specific rows, the row with the highest Buy price and the Best Seller.
    Step B: Check the "Spread" (The Stop Rule) It checks if these two prices are compatible

    The Rule: Highest Buy Price must be Lowest Sell Price - 5

    If true, the matching continues.
    If false, The gap is too wide, and the algorithm stops entirely.
    Step C: Compare Volumes & Delete. Since Sell volumes are negative (e.g., -100), the algorithm adds them together to see what is left over.
    """),
    

    html.Div([
        html.Img(id='strip-plot_v3', style={'width': '48%', 'display': 'inline-block'})
    ], style={'textAlign': 'center'}),
    
    dcc.Markdown("### Final Cleaned Data Overview"),
    dcc.Markdown("""
    As we can observe the process tend to put the Long Bids at lower prices and sell bids at higher.
    """),
    html.Img(
        src=final_scatter_img, 
        style={'width': '100%', 'marginTop': '20px', 'marginBottom': '40px'}
    ),
    
    dcc.Markdown("""
    ### Forecast Optimization
    
    Now we have to adapt the prices to the forecast. We set an upper and a lower bond of 10%.
    """),
    
    html.Img(
        src=forecast_img, 
        style={'width': '100%', 'marginBottom': '40px'}
    ),
    
    dcc.Markdown("""

    it is also import to see the forecast and the previuos bids visualization.
    """),
    
    html.Img(
        src=bids_forecast_img, 
        style={'width': '100%', 'marginBottom': '40px'}
    ),
    
    dcc.Markdown("""
    For the forecast optimization we will calculate the following variables:

    * Distance: Distance from the bid Price to the spot forecast
    * weight:  the volume ponderation from the hour
    * on range: a variable that takes value 1 when the Price is on range. 
    """),
    
    dcc.Markdown("### Forecast Optimization Variables"),
    
    dcc.Markdown("### Hourly Optimization Details "),
    dcc.Markdown("This table shows the raw calculations for 'weight' and 'weighted distance' used to select the optimal bid for each hour."),
    
    dash_table.DataTable(
        id='static-forecast-table',
        # Set columns and data directly from the DataFrame
        columns=[{"name": i, "id": i} for i in bids_forecast_temp2.columns],
        data=bids_forecast_temp2.to_dict('records'),
        
        # Add features for large datasets
        page_size=15,               # Number of rows per page
        sort_action="native",       # Allow user to sort columns
        
        # Styling
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'left',
            'padding': '10px',
            'fontFamily': 'sans-serif'
        },
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold'
        }
    ),
 
    dcc.Markdown("""
    For every hour we select the row with the highest distance_weigthed.  
    
    As we can see in the plot only the most relevant according to Volume and lower distance to the forecast take place.  
    
    Additionally, this operation get all the Volume from the other operations.
    """),
    dcc.Markdown("#### Example for hour 1 and buy bid"),
            dash_table.DataTable(
                id='temp1-table',
                columns=[{"name": i, "id": i} for i in temp1.columns],
                data=temp1.to_dict('records'),
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'padding': '5px'},
                page_size=5
            ),

    dcc.Markdown("## Buy Strategy based on Forecast"),
    dcc.Markdown("""
    This visualization displays the optimized buy orders. 
    Larger bubbles indicate hours with higher volume requirements, positioned relative to the market forecast.
    """),
    

    html.Img(
        src=final_buy_plot_img, 
        style={'width': '100%', 'marginBottom': '40px'}
    ),
    dcc.Markdown("## Sell Strategy based on Forecast"),
    dcc.Markdown("""
    Similar to the buy strategy, this visualization displays the optimized **Buy orders**. 
    """),
    html.Img(
        src=final_sell_plot_img, 
        style={'width': '100%', 'marginBottom': '40px'}
    ),
    dcc.Markdown("""
    ## Similarity
                 
    Since there are more prices than required, in this section we calculate the top 20 similar prices. 

    To start, first it is important to sort the prices and then calculate the difference, the idea is create blocks or group of prices that are similar to one another"""),
    
    
            
    dcc.Markdown("""
    To get the 20 blocks, we iterate until we find the price difference that works as a threshold.
    
    After applying the algorithm the threshold indicates that with a price difference of 3 we get 19 blocks. 
    
    ### Update Prices
    
    Finally, we create the "block price" selecting the operation price from the closest distance to the forecast.
    """),
    dcc.Markdown("#### Significant Buy Price Gaps (temp2)"),
            dash_table.DataTable(
                id='temp2-table',
                columns=[{"name": i, "id": i} for i in temp2.columns],
                data=temp2.to_dict('records'),
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'padding': '5px'},
                page_size=5
            ),
    
    dcc.Markdown("### This table shows the buy bids ordered by price"),
    
    dash_table.DataTable(
        id='buy-strategy-table',
        # Map the columns and data from your existing bids_buy_forecast_final DF
        columns=[{"name": i, "id": i} for i in bids_buy_forecast_final_temp.columns],
        data=bids_buy_forecast_final.to_dict('records'),
        
        # Adding interactivity for the user
        page_size=12,               # Shows 12 hours at a time (half the day)
        sort_action="native",       # Allows clicking headers to sort
        filter_action="native",     # Allows searching/filtering within the table
        
        # Styling to match your dashboard
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'left',
            'padding': '10px',
            'fontFamily': 'sans-serif'
        },
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold'
        }
    ),
    dcc.Markdown("## Final Optimized Strategy for Buy Bids"),
    
    
    dash_table.DataTable(
        id='buy-strategy-table2',
        # Map the columns and data from your existing bids_buy_forecast_final DF
        columns=[{"name": i, "id": i} for i in bids_buy_forecast_final2_temp.columns],
        data=bids_buy_forecast_final.to_dict('records'),
        
        # Adding interactivity for the user
        page_size=12,               # Shows 12 hours at a time (half the day)
        sort_action="native",       # Allows clicking headers to sort
        filter_action="native",     # Allows searching/filtering within the table
        
        # Styling to match your dashboard
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'left',
            'padding': '10px',
            'fontFamily': 'sans-serif'
        },
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold'
        }
    ),
    
    
    dcc.Markdown("## Final Optimized Strategy: Buy vs. Sell"),
    dcc.Markdown("""
    This plot provides the complete overview of the optimized bidding strategy. 
    By overlaying both **Buy** (Blue) and **Sell** (Orange) positions against the **Spot Forecast** (Red), 
    we can visualize the "spread" and ensure the operations align with market expectations.
    """),

    html.Img(
        src=final_buy_strategy_img, 
        style={'width': '100%', 'marginBottom': '40px'}
    ),
    
    dcc.Markdown("""
    ## Pros and Cons
    
    **Pros:**
    * This system keeps the integrity in the bids aligning the different strategies to be executed with a similar price.
    * Additionally, it takes into consideration the forecast curve and the business logic on the trades, avoiding buy orders too high and selling too low.
    * If the restrictions from EPEX changed, this system can run without further modifications.
    
    **Cons:**
    * There are fewer bids after finishing the process and less volume because of the first process.
    * It doesn't take into consideration the volume available. To solve this, another iteration algorithm can be performed to distribute volume.
    """)
])

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8081)