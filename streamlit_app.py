import base64
from pathlib import Path

import streamlit as st


BACKGROUND_IMAGE = Path(__file__).parent / "assets" / "connfas-network.jpg"

st.set_page_config(
    page_title="Connfas",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="collapsed",
)

image_data = base64.b64encode(BACKGROUND_IMAGE.read_bytes()).decode("ascii")

st.markdown(
    f"""
    <style>
        #MainMenu, footer, [data-testid="stHeader"] {{
            visibility: hidden;
        }}

        [data-testid="stAppViewContainer"] {{
            min-height: 100vh;
            background:
                linear-gradient(115deg, rgba(3, 12, 25, 0.82), rgba(4, 31, 54, 0.54)),
                url("data:image/jpeg;base64,{image_data}") center / cover fixed;
        }}

        [data-testid="stMain"] {{
            background: transparent;
        }}

        .block-container {{
            max-width: 760px;
            min-height: 100vh;
            padding: 2rem 1.5rem;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}

        .brand-kicker {{
            color: #9be7ff;
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.28em;
            margin: 0 0 0.8rem;
            text-transform: uppercase;
        }}

        .hero-content {{
            margin: 0 auto;
            text-align: center;
            width: 100%;
        }}

        .hero-title {{
            color: #ffffff !important;
            font-size: clamp(3.5rem, 12vw, 6.5rem) !important;
            font-weight: 750 !important;
            letter-spacing: -0.065em !important;
            line-height: 1 !important;
            margin: 0 0 1.1rem !important;
        }}

        .hero-copy {{
            box-sizing: border-box;
            color: rgba(239, 248, 255, 0.86);
            margin: 0 auto 2.5rem;
            font-size: clamp(1rem, 2.5vw, 1.25rem);
            line-height: 1.65;
            max-width: none;
            text-align: center !important;
            white-space: nowrap;
            width: 100%;
        }}

        [data-testid="stButton"] button {{
            border: 1px solid rgba(255, 255, 255, 0.7);
            border-radius: 999px;
            font-weight: 650;
            min-height: 3.15rem;
            transition: transform 150ms ease, background-color 150ms ease;
        }}

        [data-testid="stButton"] button:hover {{
            transform: translateY(-2px);
        }}

        [data-testid="stButton"] button[kind="primary"] {{
            background: #b9efff;
            border-color: #b9efff;
            color: #08243a;
        }}

        [data-testid="stButton"] button[kind="secondary"] {{
            background: rgba(4, 19, 35, 0.26);
            color: #ffffff;
        }}

        [data-testid="stAlert"] {{
            background: rgba(7, 25, 42, 0.88);
            color: #ffffff;
        }}

        @media (max-width: 520px) {{
            .block-container {{
                padding: 1.25rem;
            }}
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero-content">
        <div class="brand-kicker">Social, made simpler</div>
        <h1 class="hero-title">Connfas</h1>
        <p class="hero-copy">Turn your ideas into thoughtful posts and share them with the people who matter.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

sign_in_column, sign_up_column = st.columns(2, gap="medium")
with sign_in_column:
    sign_in_clicked = st.button("Sign in", type="primary", use_container_width=True)
with sign_up_column:
    sign_up_clicked = st.button("Sign up", type="secondary", use_container_width=True)

if sign_in_clicked:
    st.session_state["auth_notice"] = "Sign in is not connected yet."
elif sign_up_clicked:
    st.session_state["auth_notice"] = "Sign up is not connected yet."

if notice := st.session_state.get("auth_notice"):
    st.info(f"{notice} The current backend does not yet include app-user authentication.")
