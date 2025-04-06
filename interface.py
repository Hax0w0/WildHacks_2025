import streamlit as st

if 'page' not in st.session_state:
    st.session_state.page = 'login'

def switch_to_dashboard():
    st.session_state.page = 'dashboard'

def show_login():
    st.title("ValorAnalytics")
    st.header("Enter Your Riot ID")

    riot_name = st.text_input("Riot Name (e.g., Player123)", max_chars=16, key='riot_name')
    tagline = st.text_input("Tagline (e.g., EUW)", max_chars=5, key='tagline')

    if riot_name and tagline:
        st.button("Continue to Dashboard", on_click=switch_to_dashboard)
    else:
        st.warning("Please enter both fields to continue.")

def show_dashboard():
    st.title("📊 Player Dashboard")
    st.success(f"Welcome, {st.session_state.riot_name}#{st.session_state.tagline}")

    # Sample dashboard content
    st.metric("Matches Analyzed", "12")
    st.metric("Win Rate", "58%")
    st.metric("Top Agent", "Jett")

# Render based on current page
if st.session_state.page == 'login':
    show_login()
elif st.session_state.page == 'dashboard':
    show_dashboard()
