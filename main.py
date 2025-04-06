import io
import os
import html
import requests
from PIL import Image
import streamlit as st
from dotenv import load_dotenv
import plotly.graph_objects as go
import google.generativeai as genai
from streamlit_lottie import st_lottie

load_dotenv()  # take environment variables from .env

riotKey = os.getenv("RIOT_KEY")
geminiKey = os.getenv("GEMINI_KEY")

genai.configure(api_key=geminiKey)
model = genai.GenerativeModel('gemini-2.0-flash')

systemPrompt = """You are a Valorant analyst reviewing a scatterplot of spike plants insights during match on {map}.  
Each image shows player positions at the time of the spike plant:
- Red dots = Opposing Team
- Blue dots = Player's Team
- The player you are analyzing is {job} Site {site}.

Ignore the top two most dots in the right corner of the image.

Please analyze:
1. Common defensive positioning errors
2. Missed choke control or flank coverage
3. Suggested better spots to delay or deny the plant
4. Whether the defense is stacked or spread too thin
5. Any obvious attacker tendencies to exploit
6. Any way that the player and their team could have better positioned themselves  

Keep your response to 5 bullet points. Format them as a list without the bullet points but still the bold title followed by normal text.
The spike has just been planted, so attackers are likely to be positioned in post-plant setups.
- Attackers should be in post-plant positions, such as on-site or near the bomb, to cover the spike.
- Defenders should be rotating quickly or already in positions to retake or deny the plant.
- Evaluate whether defenders are arriving too late, caught out of position, or missing critical map control.
"""

mapPrompt = {"Icebox": """ 
             
             Map Info: This match is played on Icebox. Use accurate site-specific callouts from the Valorant map Icebox. The two bomb sites have these key locations:
                        - **A Site**: Nest, Rafters, Default, Pipes, Screens, Belt, Maze
                        - **B Site**: Yellow, Snowman, Green, Backsite, B Default, B Long, Kitchen
                        -Callout Reference (Icebox-specific Post-Plant Positions):
                        A Site:
                        -  Attackers often hold post-plant from:
                        -  Rafters (top of site, long sightline to plant)
                        -  Belt (A main high ground — good angle for post-plant)
                        -  Nest (upper mid connector)
                        -  A Pipes (for lurk control or flank watch)
                        -  Backsite / Generator (safe corner for holding close)
                        -  Defenders typically retake from:
                        -  Heaven / Rafters (if controlled or retaken)
                        -  A Pipes / Nest (flank or vertical pressure)
                        -  A Site Box (close retake or last-ditch defense)
                        -  Mid / Tube (if pushing for a flank retake)
                        B Site:
                            Attackers often hold post-plant from:
                            -Yellow (main cover object attackers hold from)
                            -Snowman (deep behind site on attacker side)
                            -B Long / B Green (post up for long-range hold)
                            -Kitchen / Tube Exit (off-angles or lurks)
                            -Mid (crossfires or late lurks)
                            Defenders typically retake from:
                            -Snowman (if retaking fast or pre-positioned)
                            -B Back / Defender Spawn (rotate entry point)
                            -Tube / Kitchen (mid push/flank)
                            -Backsite Boxes (for sneaky or aggressive defuses)
                            -Default Wall (hard defuse angle)""", 

            "Split": """ 
            
            Map Info: This match is played on Split. Use accurate site-specific callouts from the Valorant map Icebox. The two bomb sites have these key locations:
                        - **A Site**: Back, A Site, Default, A main, A Ramps, A lobby, A Tower, A Screens, A Rafters, A Sewers.
                        - **B Site**: B Stairs, B Tower, B Rafters, B site, B Default, B Back, Garage, Mid Mail, Mid Top, Mid Bottom, B Link, B Lobby, Mid Vent, B Alley, Defender Spawn.
                        -Callout Reference (Split-specific Post-Plant Positions):
                        A Site:
                        -  Attackers often hold post-plant from:
                        -  A Rafters (top of site, long sightline to plant)
                        -  A Site 
                        -  A Tower (upper mid connector)
                        -  A Main (for lurk control or flank watch)
                        -  A Back (safe corner for holding close)
                        -  Defenders typically retake from:
                        -  A Rafters (if controlled/retaken)
                        -  A Tower / Nest 
                        -  A Screens 
                        -  A Main (if pushing for a flank retake)
                        
                      
                        B Site:
                            Attackers often hold post-plant from:
                            -B Back (main cover object attackers hold from)
                            -B Tower 
                            -B Main (post up for long-range hold)
                            -B Alley 
                            -B Stairs
                            -B Tower
                            Defenders typically retake from:
                            -Defender Spawn 
                            -B Alley / Defender Spawn (rotate entry point)
                            -B stairs / B Tower / Mail / Mid Top (mid push/ defender spawn push)
                            -B Main / B Lobby (for mid push/flank)
                            -B Rafters  (coming from B tower)"""}

MAP_BOUNDS = {
                "Split": {"x_min": -3447,
                         "x_max": 8258,
                         "y_min": -10007,
                         "y_max": 914,
                         "img_width": 460,
                         "img_height": 460
                         },

                "Icebox": {"x_min": -9257,
                           "x_max": 4062,
                           "y_min": -6142,
                           "y_max": 8156,
                           "img_width": 490,
                           "img_height": 490
                           }
}

def map_to_image_coords(x_game, y_game, map_bounds, map):

    # Calculate the center of the game world
    x_scale = map_bounds["x_max"] - map_bounds["x_min"]
    y_scale = map_bounds["y_max"] - map_bounds["y_min"]
    
    # Scale the shifted coordinates to image coordinates
    if map == "Icebox":
        x_img = 510 - (x_game - map_bounds["x_min"]) / x_scale * map_bounds["img_height"]
        y_img = 490 - (y_game - map_bounds["y_min"]) / y_scale * map_bounds["img_width"]
    else:
        x_img = 10 + (x_game - map_bounds["x_min"]) / x_scale * map_bounds["img_height"]
        y_img = 30 + (y_game - map_bounds["y_min"]) / y_scale * map_bounds["img_width"]
    
    # Return image coordinates as integers
    return int(x_img), int(y_img)

class Player:
    def __init__(self, riot_ID, tagline):
        response = requests.get(
        "https://api.henrikdev.xyz/valorant/v1/account/{}/{}".format(riot_ID, tagline),
        headers={"Authorization": riotKey})

        if response.status_code != 200:
            print("Error: Unable to fetch data from API")
            return
        
        data = response.json()
        
        self.name = riot_ID
        self.tagline = tagline
        self.puuid = data["data"]["puuid"]
        self.region = data["data"]["region"].upper()
        self.level = data["data"]["account_level"]
        self.card = data["data"]["card"]["small"]
        self.winrate = {'Competitive': 0, 'Unrated': 0} 
        self.get_match_history()

        self.matchdata = {'first_half_red_A': [], 'first_half_blue_A': [], 'first_half_red_B': [], 'first_half_blue_B': [], 
                          'second_half_red_A': [], 'second_half_blue_A': [], 'second_half_red_B': [], 'second_half_blue_B': []}

    def get_match(self, mode):
        # Create the URL and get the response
        url = "https://api.henrikdev.xyz/valorant/v3/by-puuid/matches/{}/{}?mode={}&size=1".format(self.region, self.puuid, mode.lower())
        response = requests.get(url, headers={"Authorization": riotKey})
        if response.status_code != 200:
            print("Error: Unable to fetch match data")
            return
        
        data = response.json()
        return data
    
    def get_match_history(self):
        # Create the URL and get the response
        url = "https://api.henrikdev.xyz/valorant/v1/stored-matches/{}/{}/{}".format(self.region, self.name, self.tagline)
        response = requests.get(url, headers={"Authorization": riotKey})
        if response.status_code != 200:
            print("Error: Unable to fetch match history")
            return
        
        data = response.json()

        if data['status'] != 200:
            print("Error: Unable to fetch match history")
            return
        
        history = data['data']

        # Calculate winrate
        games_played = {'Competitive': 0, 'Unrated': 0}
        for i in range(len(history)):
            if (history[i]['stats']['team'] == 'Blue' and history[i]['teams']['blue'] > history[i]['teams']['red']) or (history[i]['stats']['team'] == 'Red' and history[i]['teams']['red'] > history[i]['teams']['blue']):
                if history[i]['meta']['mode'] == "Competitive":
                    self.winrate['Competitive'] += 1
                else:
                    self.winrate['Unrated'] += 1
            try:
                games_played[history[i]['meta']['mode']] += 1 if history[i]['meta']['mode'] == "Competitive" or history[i]['meta']['mode'] == "Unrated" else 0
            except KeyError:
                continue

        for j in self.winrate:
            self.winrate[j] = round((self.winrate[j] / games_played[j]) * 100, 2) if games_played[j] != 0 else 0

    def create_scatterplot(self, map, positions_red, positions_blue, site, half):
        map_bounds = MAP_BOUNDS[map]

        red_pos = [map_to_image_coords(x, y, map_bounds, map) for x, y in positions_red]
        blue_pos = [map_to_image_coords(x, y, map_bounds, map) for x, y in positions_blue]

        if site == 'A' and half == 'first_half':
            self.matchdata['first_half_red_A'] = red_pos
            self.matchdata['first_half_blue_A'] = blue_pos
        elif site == 'B' and half == 'first_half':
            self.matchdata['first_half_red_B'] = red_pos
            self.matchdata['first_half_blue_B'] = blue_pos
        elif site == 'A' and half == 'second_half':
            self.matchdata['second_half_red_A'] = red_pos
            self.matchdata['second_half_blue_A'] = blue_pos
        else:
            self.matchdata['second_half_red_B'] = red_pos
            self.matchdata['second_half_blue_B'] = blue_pos
    
    def create_scatterplot_plants(self, mode):
        match = self.get_match(mode)
        map = match["data"][0]["metadata"]["map"]

        first_half_red_A, first_half_blue_A, first_half_red_B, first_half_blue_B = self.create_scatterplot_first_half(match)

        self.create_scatterplot(map, first_half_red_A, first_half_blue_A, 'A', 'first_half')
        self.create_scatterplot(map, first_half_red_B, first_half_blue_B, 'B', 'first_half')

        second_half_red_A, second_half_blue_A, second_half_red_B, second_half_blue_B = self.create_scatterplot_second_half(match)

        self.create_scatterplot(map, second_half_red_A, second_half_blue_A, 'A', 'second_half')
        self.create_scatterplot(map, second_half_red_B, second_half_blue_B, 'B', 'second_half')

    def create_scatterplot_first_half(self, match):
        # Get rounds where the spike was planted on the site
        rounds = match["data"][0]["rounds"]

        # Calculate the number of rounds there are
        num_rounds = len(rounds)

        # Calculate what happens in the first half
        first_half_red_A = []
        first_half_blue_A = []

        first_half_red_B = []
        first_half_blue_B = []

        for i in range(12):

            round = rounds[i]

            if round["bomb_planted"] == True and round["plant_events"]["plant_site"] == "A":
                players = round["plant_events"]["player_locations_on_plant"]

                for player in players:
                    player_team = player["player_team"]
                    loc = player["location"]

                    if player_team == "Red":
                        first_half_red_A.append((int(loc["x"]), int(loc["y"])))
                    else:
                        first_half_blue_A.append((int(loc["x"]), int(loc["y"])))

            if round["bomb_planted"] == True and round["plant_events"]["plant_site"] == "B":
                players = round["plant_events"]["player_locations_on_plant"]

                for player in players:
                    player_team = player["player_team"]
                    loc = player["location"]

                    if player_team == "Red":
                        first_half_red_B.append((int(loc["x"]), int(loc["y"])))
                    else:
                        first_half_blue_B.append((int(loc["x"]), int(loc["y"])))

        return first_half_red_A, first_half_blue_A, first_half_red_B, first_half_blue_B
    
    def create_scatterplot_second_half(self, match):
        # Get rounds where the spike was planted on the site
        rounds = match["data"][0]["rounds"]

        # Calculate the number of rounds there are
        num_rounds = len(rounds)

        # Calculate what happens in the second half
        second_half_red_A = []
        second_half_blue_A = []

        second_half_red_B = []
        second_half_blue_B = []

        for i in range(12, num_rounds):

            round = rounds[i]

            if round["bomb_planted"] == True and round["plant_events"]["plant_site"] == "A":
                players = round["plant_events"]["player_locations_on_plant"]

                for player in players:
                    player_team = player["player_team"]
                    loc = player["location"]

                    if player_team == "Red":
                        second_half_red_A.append((int(loc["x"]), int(loc["y"])))
                    else:
                        second_half_blue_A.append((int(loc["x"]), int(loc["y"])))

            if round["bomb_planted"] == True and round["plant_events"]["plant_site"] == "B":
                players = round["plant_events"]["player_locations_on_plant"]

                for player in players:
                    player_team = player["player_team"]
                    loc = player["location"]

                    if player_team == "Red":
                        second_half_red_B.append((int(loc["x"]), int(loc["y"])))
                    else:
                        second_half_blue_B.append((int(loc["x"]), int(loc["y"])))

        return second_half_red_A, second_half_blue_A, second_half_red_B, second_half_blue_B
















# Streamlit app
st.set_page_config(page_title="ValorAnalytics", page_icon="🎯", layout="wide")

st.markdown("""
        <style>
               .block-container {
                    padding-top: 1rem;
                    padding-bottom: 0rem;
                    padding-left: 5rem;
                    padding-right: 5rem;
                }
            
                div[data-testid="stSidebarHeader"] {
                    padding-top: 10px !important;
                    padding-bottom: 0px !important;
                }
        </style>
        """, unsafe_allow_html=True)

if 'page' not in st.session_state:
    st.session_state.page = 'login'

def switch_to_dashboard():
    st.session_state.riot_name = st.session_state.riot_name
    st.session_state.tagline = st.session_state.tagline
    st.session_state.page = 'dashboard'

def show_login():
    st.title("🎯 ValorAnalytics 🎯")
    st.header("Enter Your Riot ID")

    text1, text2, text3, text4 = st.columns(4)
    with text2:
        riot_name = st.text_input("Riot Name (e.g., Player123)", max_chars=16, key='riot_name')
    with text3:
        tagline = st.text_input("Tagline (e.g., EUW)", max_chars=5, key='tagline')

    button_col = st.columns([1, 2, 1])  # Three columns, middle one is wider
    with button_col[1]:
        if riot_name and tagline:
            st.button("Continue to Dashboard", on_click=switch_to_dashboard, use_container_width=True)
        else:
            st.warning("Please enter both fields to continue.", icon="⚠️")

def show_dashboard():
    # Avoid double-instantiation of Player object
    if 'player' not in st.session_state:
        st.session_state.player = Player(st.session_state.riot_name, st.session_state.tagline)

    # Contents
    with st.sidebar:
        st.markdown("<h1 style='text-align: center; padding-top: 0px;'>{}</h1>".format("{}#{}".format(st.session_state.player.name, st.session_state.player.tagline)), unsafe_allow_html=True)
        
        image1, image2, image3 = st.columns([1, 3, 1])
        with image2:
            st.image(st.session_state.player.card, use_container_width=True)

        modes = ["Competitive", "Unrated"]
        selected_mode = st.selectbox("Select a mode", modes, index=0)

        sides = ["Attacker", "Defender"]
        selected_side = st.selectbox("Select a side", sides, index=1)

        site = ["A", "B"]
        selected_site = st.selectbox("Select a site", site, index=0)

    st.title("🎯 ValorAnalytics 🎯")
    render_contents(selected_mode, selected_side, selected_site)
    

def render_contents(selected_mode, selected_side, selected_site):
    col = st.columns((4.5, 2), gap='medium')
    with col[0]:
        with st.expander(label="Most Recent Match Analysis: {} Site {}".format("Defending" if selected_side == "Defender" else "Attacking", selected_site), icon="🔎", expanded=True):
            match = st.session_state.player.get_match(selected_mode)

            if match is None:
                st.error("Unable to fetch match data.")
                return
            
            map_image_url = "https://imgsvc.trackercdn.com/url/max-width(1656),quality(70)/https%3A%2F%2Ftrackercdn.com%2Fcdn%2Ftracker.gg%2Fvalorant%2Fdb%2Fmaps%2F9.08%2Ficebox.png/image.png" if match["data"][0]["metadata"]["map"] == "Icebox" else "https://imgsvc.trackercdn.com/url/max-width(1656),quality(70)/https%3A%2F%2Ftrackercdn.com%2Fcdn%2Ftracker.gg%2Fvalorant%2Fdb%2Fmaps%2F9.08%2Fsplit.png/image.png"
            
            response = requests.get(map_image_url)
            image_pil = Image.open(io.BytesIO(response.content))

            st.session_state.player.create_scatterplot_plants(selected_mode)
            positions_red = []
            positions_blue = []

            if selected_side == "Defender" and selected_site == "A":
                for i in range(len(st.session_state.player.matchdata['first_half_red_A'])):
                    positions_red.append({"x": st.session_state.player.matchdata['first_half_red_A'][i][0], "y": st.session_state.player.matchdata['first_half_red_A'][i][1], "label": ""})
                for i in range(len(st.session_state.player.matchdata['first_half_blue_A'])):
                    positions_blue.append({"x": st.session_state.player.matchdata['first_half_blue_A'][i][0], "y": st.session_state.player.matchdata['first_half_blue_A'][i][1], "label": ""})
            elif selected_side == "Defender" and selected_site == "B":
                for i in range(len(st.session_state.player.matchdata['first_half_red_B'])):
                    positions_red.append({"x": st.session_state.player.matchdata['first_half_red_B'][i][0], "y": st.session_state.player.matchdata['first_half_red_B'][i][1], "label": ""})
                for i in range(len(st.session_state.player.matchdata['first_half_blue_B'])):
                    positions_blue.append({"x": st.session_state.player.matchdata['first_half_blue_B'][i][0], "y": st.session_state.player.matchdata['first_half_blue_B'][i][1], "label": ""})
            elif selected_side == "Attacker" and selected_site == "A":
                for i in range(len(st.session_state.player.matchdata['second_half_red_A'])):
                    positions_red.append({"x": st.session_state.player.matchdata['second_half_red_A'][i][0], "y": st.session_state.player.matchdata['second_half_red_A'][i][1], "label": ""})
                for i in range(len(st.session_state.player.matchdata['second_half_blue_A'])):
                    positions_blue.append({"x": st.session_state.player.matchdata['second_half_blue_A'][i][0], "y": st.session_state.player.matchdata['second_half_blue_A'][i][1], "label": ""})
            elif selected_side == "Attacker" and selected_site == "B":
                for i in range(len(st.session_state.player.matchdata['second_half_red_B'])):
                    positions_red.append({"x": st.session_state.player.matchdata['second_half_red_B'][i][0], "y": st.session_state.player.matchdata['second_half_red_B'][i][1], "label": ""})
                for i in range(len(st.session_state.player.matchdata['second_half_blue_B'])):
                    positions_blue.append({"x": st.session_state.player.matchdata['second_half_blue_B'][i][0], "y": st.session_state.player.matchdata['second_half_blue_B'][i][1], "label": ""})

            fig = go.Figure()

            # Add background map
            fig.add_layout_image(
            dict(
                source=image_pil,  # this now works with write_image()
                xref="x",
                yref="y",
                x=0,
                y=0,
                sizex=500,
                sizey=500,
                sizing="stretch",
                layer="below"
            )
        )

            # Add red markers
            fig.add_trace(go.Scatter(
                x=[pos["x"] for pos in positions_red],
                y=[pos["y"] for pos in positions_red],
                mode="markers+text",
                name="Opponent Team",
                textposition="top center",
                marker=dict(size=12, color="red")
            ))

            # Add blue markers
            fig.add_trace(go.Scatter(
                x=[pos["x"] for pos in positions_blue],
                y=[pos["y"] for pos in positions_blue],
                mode="markers+text",
                name="Your Team",
                textposition="top center",
                marker=dict(size=12, color="blue")
            ))

            # Fix axes
            fig.update_layout(
                xaxis=dict(visible=False, range=[0, 500]),
                yaxis=dict(visible=False, range=[500, 0]),  # flipped Y-axis to match image
                margin=dict(l=0, r=0, t=0, b=0),
                height=500,
                width=500,
                showlegend=False,
            )

            # Save chart as image
            fig.write_image("scatterplot.png", format="png", scale=3)

            fig.update_layout(
                annotations=[
                    dict(
                        x=0.95,  # Position of the custom legend (relative to the plot area)
                        y=0.97,  # Position of the custom legend
                        xref="paper",  # Use paper coordinates (0 to 1) for positioning
                        yref="paper",  # Use paper coordinates for positioning
                        text="Opponent Team",  # Text for the legend entry
                        showarrow=False,  # No arrow
                        font=dict(size=12, color="#777"),  # Font settings
                        align="left"  # Text alignment
                    ),
                    dict(
                        x=0.95,
                        y=0.94,
                        xref="paper",
                        yref="paper",
                        text="Your Team",
                        showarrow=False,
                        font=dict(size=12, color="#777"),
                        align="left"
                    )
                ],
                shapes=[
                    # Red circle for Opponent Team
                    dict(
                        type="circle",
                        xref="paper",  # Paper coordinates for positioning
                        yref="paper",
                        x0=0.766,  # Adjusted position to the left of the text
                        y0=0.94,
                        x1=0.786,  # Size of the circle
                        y1=0.96,
                        line=dict(color="red", width=2),
                        fillcolor="red"
                    ),
                    # Blue circle for Your Team
                    dict(
                        type="circle",
                        xref="paper",  # Paper coordinates for positioning
                        yref="paper",
                        x0=0.82,  # Adjusted position to the left of the text
                        y0=0.91,
                        x1=0.84,  # Size of the circle
                        y1=0.93,
                        line=dict(color="blue", width=2),
                        fillcolor="blue"
                    )
                ]
            )

            st.plotly_chart(fig)

    with col[1]:
        with st.expander(label="Overview", icon="📋", expanded=True):
            smolcol = st.columns([0.1, 1, 0.1])
            with smolcol[1]:
                fig = go.Figure(go.Pie(
                    labels=["Win", "Loss"],
                    values=[st.session_state.player.winrate[selected_mode], 100 - st.session_state.player.winrate[selected_mode]],
                    showlegend=False,
                    sort=False,
                    textinfo="none",
                    opacity=0.7,
                    hole=0.55,
                    insidetextorientation="radial",
                    marker=dict(colors=["#28b297", "#4d4d4d"])
                ))

                fig.add_annotation(
                    text=f"<b>Win Rate</b><br>{st.session_state.player.winrate[selected_mode]}%",  # Title and percentage value
                    x=0.5,  # Center of the ring
                    y=0.5,  # Center of the ring
                    showarrow=False,
                    font=dict(size=24, color="white"),  # Font size and color
                    align="center",
                    valign="middle",  # Vertical alignment to center the text
                )

                # Clean layout, remove all margins, and fix aspect ratio
                fig.update_layout(
                    margin=dict(l=0, r=0, t=0, b=0),
                    height=150,  # Adjust height to desired compactness
                    width=150,   # Square for perfect donut shape
                    paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
                    plot_bgcolor="rgba(0,0,0,0)"
                )

                st.plotly_chart(fig, use_container_width=False)

        with st.expander(label="AI Analysis", icon="🤖", expanded=True):
            st.markdown(
                """
                <style>
                .scrollable-container {
                    height: 255px;
                    overflow-y: auto;
                    padding-right: 10px;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

            graph = Image.open("scatterplot.png")

            response = model.generate_content([
                systemPrompt.format(
                    map=match["data"][0]["metadata"]["map"],
                    job="defending" if selected_side == "Defender" else "attacking",
                    site=selected_site
                ) + mapPrompt[match["data"][0]["metadata"]["map"]],
                graph
            ])

            # Wrap the AI response in the scrollable div
            st.markdown(
                f"""
                <div class="scrollable-container">
                <pre>{html.escape(response.text)}</pre>
                </div>
                """,
                unsafe_allow_html=True
            )

            
# Render based on current page
if st.session_state.page == 'login':
    show_login()
elif st.session_state.page == 'dashboard':
    show_dashboard()