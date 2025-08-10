from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
from datetime import datetime, timedelta
import pybaseball as pyb
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.lines import Line2D
import seaborn as sns
import io
import base64

app = Flask(__name__)
CORS(app)

# Constants
BALL_RADIUS = 0.1208

# Pitch colors from your original code
PITCH_COLORS = {
    'FF': '#D62828', 'SI': '#F77F00', 'FC': '#7F4F24', 'CH': '#43AA8B',
    'FS': '#3A9D9A', 'FO': '#4ECDC4', 'SC': '#90BE6D', 'CU': '#48CAE4',
    'KC': '#6930C3', 'CS': '#3A0CA3', 'SL': '#F9C74F', 'ST': '#F8961E', 'SV': '#90A0C0'
}

# Enhanced team mapping for better accuracy
TEAM_MAPPING = {
    'LAA': 'LAA', 'ANA': 'LAA',  # Angels
    'HOU': 'HOU',                 # Astros
    'OAK': 'OAK',                 # Athletics
    'SEA': 'SEA',                 # Mariners
    'TEX': 'TEX',                 # Rangers
    'CWS': 'CWS', 'CHW': 'CWS',  # White Sox
    'CLE': 'CLE',                 # Guardians
    'DET': 'DET',                 # Tigers
    'KC': 'KC', 'KCR': 'KC',     # Royals
    'MIN': 'MIN',                 # Twins
    'NYY': 'NYY', 'NY': 'NYY',   # Yankees
    'BAL': 'BAL',                 # Orioles
    'BOS': 'BOS',                 # Red Sox
    'TB': 'TB', 'TBR': 'TB',     # Rays
    'TOR': 'TOR',                 # Blue Jays
    'ATL': 'ATL',                 # Braves
    'MIA': 'MIA', 'FLA': 'MIA',  # Marlins
    'NYM': 'NYM',                 # Mets
    'PHI': 'PHI',                 # Phillies
    'WSH': 'WSH', 'WAS': 'WSH',  # Nationals
    'CHC': 'CHC', 'CHI': 'CHC',  # Cubs
    'CIN': 'CIN',                 # Reds
    'MIL': 'MIL',                 # Brewers
    'PIT': 'PIT',                 # Pirates
    'STL': 'STL',                 # Cardinals
    'ARI': 'ARI', 'AZ': 'ARI',   # Diamondbacks
    'COL': 'COL',                 # Rockies
    'LAD': 'LAD', 'LA': 'LAD',   # Dodgers
    'SD': 'SD', 'SDP': 'SD',     # Padres
    'SF': 'SF', 'SFG': 'SF'      # Giants
}

def get_player_name(player_id):
    """Get player name from MLB API"""
    try:
        import requests
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'people' in data and len(data['people']) > 0:
                return data['people'][0]['fullName']
    except:
        pass
    return f"Player {player_id}"

def get_game_matchup(game_data):
    """Get game matchup in format 'AWAY vs HOME'"""
    try:
        if len(game_data) > 0:
            row = game_data.iloc[0]
            home_team = None
            away_team = None
            
            # Try to get home and away teams
            if 'home_team' in row and pd.notna(row['home_team']):
                home_team = TEAM_MAPPING.get(str(row['home_team']).upper().strip(), str(row['home_team']).upper().strip())
            if 'away_team' in row and pd.notna(row['away_team']):
                away_team = TEAM_MAPPING.get(str(row['away_team']).upper().strip(), str(row['away_team']).upper().strip())
                
            if home_team and away_team:
                return f"{away_team} vs {home_team}"
            elif home_team:
                return f"vs {home_team}"
            elif away_team:
                return f"{away_team} vs"
                
    except Exception as e:
        print(f"Error getting matchup: {e}")
    
    return "Game"

def get_correct_team(catcher_data):
    """Get correct team abbreviation with better logic"""
    # Get the most common team for this catcher in this game
    team_counts = {}
    
    for _, row in catcher_data.iterrows():
        # Try different team fields
        for field in ['fielding_team', 'home_team', 'away_team']:
            if field in row and pd.notna(row[field]):
                team = str(row[field]).upper().strip()
                mapped_team = TEAM_MAPPING.get(team, team)
                team_counts[mapped_team] = team_counts.get(mapped_team, 0) + 1
    
    # Return the most frequent team, or try to determine from game context
    if team_counts:
        return max(team_counts.items(), key=lambda x: x[1])[0]
    
    # Fallback: try to get from any row
    if len(catcher_data) > 0:
        row = catcher_data.iloc[0]
        for field in ['fielding_team', 'home_team', 'away_team']:
            if field in row and pd.notna(row[field]):
                team = str(row[field]).upper().strip()
                return TEAM_MAPPING.get(team, team)
    
    return "UNK"

def is_in_strike_zone(row):
    """Determine if pitch is in the true strike zone"""
    return (
        (row['plate_x'] - BALL_RADIUS <= 0.7083) &
        (row['plate_x'] + BALL_RADIUS >= -0.7083) &
        (row['plate_z'] + BALL_RADIUS >= row['sz_bot']) &
        (row['plate_z'] - BALL_RADIUS <= row['sz_top'])
    )

def is_in_shadow_zone(row):
    """Determine if pitch is in shadow zone based on Baseball Savant attack zone definitions"""
    x = row['plate_x']
    z = row['plate_z']
    sz_top = row['sz_top']
    sz_bot = row['sz_bot']
    
    # Expanded shadow zone margins
    horizontal_margin = 0.3   # About 3.6 inches
    vertical_margin = 0.4     # About 4.8 inches - bigger for top/bottom
    edge_margin = 0.2         # Borderline inside zone
    
    # Horizontal shadow zones (left and right of plate)
    in_horizontal_shadow = (
        # Right shadow (attack zone 12, 13, 14)
        ((x > 0.7083) & (x <= 0.7083 + horizontal_margin) & (z >= sz_bot - vertical_margin) & (z <= sz_top + vertical_margin)) |
        # Left shadow (attack zone 11, 16, 17) 
        ((x < -0.7083) & (x >= -0.7083 - horizontal_margin) & (z >= sz_bot - vertical_margin) & (z <= sz_top + vertical_margin))
    )
    
    # Vertical shadow zones (above and below strike zone) - EXPANDED
    in_vertical_shadow = (
        # Upper shadow (attack zone 18, 19) - bigger margin
        ((z > sz_top) & (z <= sz_top + vertical_margin) & (x >= -0.7083 - horizontal_margin) & (x <= 0.7083 + horizontal_margin)) |
        # Lower shadow - bigger margin
        ((z < sz_bot) & (z >= sz_bot - vertical_margin) & (x >= -0.7083 - horizontal_margin) & (x <= 0.7083 + horizontal_margin))
    )
    
    # Borderline inside zone (edges of zones 1, 2, 3, 4, 6, 7, 8, 9) - slightly expanded
    barely_in_zone = (
        # Right edge of zone
        ((x > 0.7083 - edge_margin) & (x <= 0.7083) & (z >= sz_bot) & (z <= sz_top)) |
        # Left edge of zone  
        ((x < -0.7083 + edge_margin) & (x >= -0.7083) & (z >= sz_bot) & (z <= sz_top)) |
        # Top edge of zone - expanded
        ((z > sz_top - edge_margin) & (z <= sz_top) & (x >= -0.7083) & (x <= 0.7083)) |
        # Bottom edge of zone - expanded
        ((z < sz_bot + edge_margin) & (z >= sz_bot) & (x >= -0.7083) & (x <= 0.7083))
    )
    
    return in_horizontal_shadow | in_vertical_shadow | barely_in_zone

def plot_gameday_summary_inferno_shadow_only(df, player_name, matchup_date):
    """Your gameday summary plot but ONLY for shadow zone pitches"""
    
    # FILTER TO SHADOW ZONES ONLY based on coordinates
    shadow_mask = df.apply(is_in_shadow_zone, axis=1)
    df = df[shadow_mask].copy()
    
    if df.empty:
        # Create empty plot if no shadow zone data
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.text(0.5, 0.5, 'No shadow zone pitch data available\n(borderline pitches)', 
                ha='center', va='center', transform=ax.transAxes, color='white')
        ax.set_facecolor('black')
        fig.patch.set_facecolor('black')
        return fig
    
    # Calculate true strike zone for shadow zone pitches
    df['true_strike'] = (
        (df['plate_x'] - BALL_RADIUS <= 0.7083) &
        (df['plate_x'] + BALL_RADIUS >= -0.7083) &
        (df['plate_z'] + BALL_RADIUS >= df['sz_bot']) &
        (df['plate_z'] - BALL_RADIUS <= df['sz_top'])
    )

    # Only called pitches in shadow zones
    called_df = df[df['description'].isin(['called_strike', 'ball'])].copy()
    
    if called_df.empty:
        # Create empty plot if no called shadow zone data
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.text(0.5, 0.5, 'No called pitches in shadow zones\n(borderline pitches)', 
                ha='center', va='center', transform=ax.transAxes, color='white')
        ax.set_facecolor('black')
        fig.patch.set_facecolor('black')
        return fig
        
    strike_kde = called_df[called_df['description'] == 'called_strike']
    
    # SHADOW ZONE CALLED STRIKE RATE
    cs_pct = len(strike_kde) / len(called_df) if len(called_df) > 0 else 0
    extra_count = len(called_df[(called_df['description'] == 'called_strike') & (~called_df['true_strike'])])
    lost_count = len(called_df[(called_df['description'] == 'ball') & (called_df['true_strike'])])

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.grid(False)

    # Original Inferno KDE Heatmap (only shadow zone strikes)
    if len(strike_kde) > 0:
        sns.kdeplot(
            x=strike_kde['plate_x'], y=strike_kde['plate_z'],
            fill=True, cmap='inferno', alpha=0.5, ax=ax, levels=100, thresh=0.05, linewidths=0
        )

    # Plot only shadow zone pitches
    for _, row in called_df.iterrows():
        color = PITCH_COLORS.get(row['pitch_type'], 'white')
        linestyle = 'solid' if row['stand'] == 'R' else (0, (1, 1, 0, 1))
        x, z = row['plate_x'], row['plate_z']
        if row['description'] == 'called_strike':
            ax.add_patch(Circle((x, z), BALL_RADIUS, edgecolor=color, facecolor=color, lw=1.5, linestyle=linestyle, alpha=0.8))
            ax.add_patch(Circle((x, z), BALL_RADIUS, edgecolor='white', facecolor='none', lw=2.2, linestyle=linestyle))
            if not row['true_strike']:
                ax.text(x, z, '*', color='white', fontsize=12, weight='bold', ha='center', va='center')
        else:
            ax.plot(x, z, marker='x', color=color, markersize=13, mew=3, alpha=0.8)
            if row['true_strike']:
                ax.text(x, z, '*', color='white', fontsize=12, weight='bold', ha='center', va='center')

    # Strike zone
    zone_top, zone_bot = 3.5, 1.5
    ax.plot([-0.7083, 0.7083], [zone_top, zone_top], color='white', lw=2, linestyle='dotted')
    ax.plot([-0.7083, 0.7083], [zone_bot, zone_bot], color='white', lw=2, linestyle='dotted')
    ax.plot([-0.7083, -0.7083], [zone_bot, zone_top], color='white', lw=2)
    ax.plot([0.7083, 0.7083], [zone_bot, zone_top], color='white', lw=2)
    ax.plot([-0.7083, 0.7083], [0.56, 0.56], color='white', lw=2)

    # Axes and styling
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(0.5, 4.5)
    ax.set_aspect('equal', adjustable='datalim')
    ax.set_xticks([-1.5, -1.0, -0.7083, -0.5, -0.25, 0, 0.25, 0.5, 0.7083, 1.0, 1.5])
    ax.set_xticklabels(['18"', '12"', 'Edge', '6"', '3"', '0"', '3"', '6"', 'Edge', '12"', '18"'])
    ax.set_xlabel("Horizontal Distance from Plate Center", fontsize=11, labelpad=12, color='white', weight='bold')
    ax.set_ylabel("Vertical Position (feet from ground)", fontsize=11, labelpad=10, color='white', weight='bold')
    ax.tick_params(color='white', labelcolor='white', width=1.5, length=6, labelsize=10)
    for spine in ax.spines.values():
        spine.set_color('white')
        spine.set_linewidth(1.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Text and annotations - UPDATED TEXT
    ax.text(0, 0.64, "Catcher's Perspective", ha='center', va='center', fontsize=9, color='white')
    anchor_x, anchor_y = 1.58, 1.25
    ax.text(anchor_x, anchor_y, "Shadow Zone CS Rate:", fontsize=10, color='white', ha='center', weight='bold')
    ax.text(anchor_x, anchor_y - 0.115, f"{cs_pct:.1%}", fontsize=14, color='white', ha='center', weight='bold')
    ax.text(anchor_x, anchor_y - 0.245, f"Extra Strikes: {extra_count}", fontsize=10, color='white', ha='center', weight='bold')
    ax.text(anchor_x, anchor_y - 0.335, f"Lost Strikes: {lost_count}", fontsize=10, color='white', ha='center', weight='bold')
    ax.text(anchor_x, anchor_y - 0.435, "*Extra/Lost Call", fontsize=8, color='white', ha='center', style='italic')
    ax.text(anchor_x, anchor_y - 0.535, f"n = {len(called_df)} pitches", fontsize=8, color='white', ha='center', style='italic')
    ax.text(-1.83, 0.68, "@KICKDIRTBB", fontsize=9, color='white', weight='bold', style='italic')

    # Title
    ax.set_title(f"{player_name}\nShadow Zone Summary - {matchup_date}",
                 fontsize=14, color='white', weight='bold', pad=20)

    # Legend
    pitch_types = sorted(df['pitch_type'].dropna().unique())
    pitch_legend = [Line2D([0], [0], marker='o', linestyle='None', label=pt,
        markerfacecolor=PITCH_COLORS.get(pt, 'white'), markeredgecolor='none', markersize=10)
        for pt in pitch_types if pt in PITCH_COLORS]
    legend_elements = pitch_legend + [
        Line2D([0], [0], marker='o', color='white', label='CS vs RHH',
               markerfacecolor='none', markeredgecolor='white', markersize=10, lw=2, linestyle='solid'),
        Line2D([0], [0], marker='o', color='white', label='CS vs LHH',
               markerfacecolor='none', markeredgecolor='white', markersize=10, lw=2, linestyle=(0, (1, 1, 0, 1))),
        Line2D([0], [0], marker='x', color='white', label='Ball',
               markersize=10, linestyle='None', markeredgewidth=2)
    ]
    ax.legend(handles=legend_elements, loc='upper left', frameon=True,
              facecolor='black', edgecolor='white', labelcolor='white').set_bbox_to_anchor((0.01, 1.01))

    fig.patch.set_facecolor('black')
    ax.set_facecolor('black')
    plt.tight_layout()
    
    return fig

@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route('/api/statcast/catchers')
def get_catchers():
    date = request.args.get('date', (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
    
    try:
        print(f"Fetching Statcast data for {date}...")
        
        # Fetch real Statcast data
        data = pyb.statcast(start_dt=date, end_dt=date)
        
        if data.empty:
            print("No data found for this date")
            return jsonify([])
        
        # Filter for called pitches with catcher data
        called_data = data[
            data['description'].isin(['called_strike', 'ball']) &
            data['fielder_2'].notna() &
            data['plate_x'].notna() &
            data['plate_z'].notna() &
            data['sz_top'].notna() &
            data['sz_bot'].notna()
        ].copy()
        
        if called_data.empty:
            return jsonify([])
        
        print(f"Found {len(called_data)} called pitches")
        
        # Add zone classifications
        called_data['in_strike_zone'] = is_in_strike_zone(called_data)
        
        # SHADOW ZONE: Based on coordinates, not zone numbers
        called_data['in_shadow_zone'] = called_data.apply(is_in_shadow_zone, axis=1)
        
        catchers = []
        
        for game_pk in called_data['game_pk'].unique():
            game_data = called_data[called_data['game_pk'] == game_pk]
            
            for catcher_id in game_data['fielder_2'].unique():
                catcher_data = game_data[game_data['fielder_2'] == catcher_id]
                
                if len(catcher_data) >= 5:  # Minimum 5 called pitches
                    
                    # SHADOW ZONE ANALYSIS (borderline pitches only)
                    shadow_pitches = catcher_data[catcher_data['in_shadow_zone']]
                    
                    if len(shadow_pitches) > 0:
                        shadow_strikes = len(shadow_pitches[shadow_pitches['description'] == 'called_strike'])
                        shadow_strike_rate = shadow_strikes / len(shadow_pitches)
                    else:
                        shadow_strike_rate = 0
                    
                    # FRAMING ANALYSIS (on all pitches)
                    # Extra strikes: called strikes that were actually balls
                    extra_strikes = len(catcher_data[
                        (catcher_data['description'] == 'called_strike') & 
                        (~catcher_data['in_strike_zone'])
                    ])
                    
                    # Lost strikes: called balls that were actually strikes  
                    lost_strikes = len(catcher_data[
                        (catcher_data['description'] == 'ball') & 
                        (catcher_data['in_strike_zone'])
                    ])
                    
                    # Total called strike rate (for reference)
                    total_called_strikes = len(catcher_data[catcher_data['description'] == 'called_strike'])
                    total_strike_rate = total_called_strikes / len(catcher_data)
                    
                    player_name = get_player_name(int(catcher_id))
                    team = get_correct_team(catcher_data)
                    matchup = get_game_matchup(catcher_data)
                    
                    catchers.append({
                        "id": int(catcher_id),
                        "player_name": player_name,
                        "team": team,
                        "matchup": matchup,
                        "date": date,
                        "game_pk": int(game_pk),
                        "called_strike_rate": round(shadow_strike_rate, 3),  # Shadow zones only
                        "total_strike_rate": round(total_strike_rate, 3),    # All pitches for reference
                        "extra_strikes": int(extra_strikes),
                        "lost_strikes": int(lost_strikes),
                        "total_called_pitches": len(catcher_data),
                        "shadow_zone_pitches": len(shadow_pitches)
                    })
        
        print(f"Returning {len(catchers)} catchers")
        return jsonify(catchers)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify([])

@app.route('/api/plot/<int:catcher_id>/<int:game_pk>')
def generate_plot(catcher_id, game_pk):
    """Generate matplotlib plot for a specific catcher/game - SHADOW ZONES ONLY"""
    date = request.args.get('date', (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
    
    try:
        print(f"Generating shadow zone plot for catcher {catcher_id}, game {game_pk}, date {date}")
        
        # Get the data for this catcher
        data = pyb.statcast(start_dt=date, end_dt=date)
        catcher_data = data[
            (data['fielder_2'] == catcher_id) & 
            (data['game_pk'] == game_pk) &
            data['description'].isin(['called_strike', 'ball']) &
            data['plate_x'].notna() &
            data['plate_z'].notna() &
            data['sz_top'].notna() &
            data['sz_bot'].notna()
        ].copy()
        
        if catcher_data.empty:
            return jsonify({'error': 'No data found for this catcher/game'}), 404
        
        print(f"Found {len(catcher_data)} total called pitches")
        
        player_name = get_player_name(catcher_id)
        
        # Generate shadow zone only plot (filtering happens inside the function)
        fig = plot_gameday_summary_inferno_shadow_only(catcher_data, player_name, date)
        
        # Convert to base64
        img_buffer = io.BytesIO()
        fig.savefig(img_buffer, format='png', bbox_inches='tight', dpi=150)
        img_buffer.seek(0)
        img_base64 = base64.b64encode(img_buffer.read()).decode()
        plt.close(fig)
        
        return jsonify({'image': f'data:image/png;base64,{img_base64}'})
        
    except Exception as e:
        print(f"Error generating plot: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')