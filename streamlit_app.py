import base64
import os
from pathlib import Path

import httpx
import streamlit as st


BACKGROUND_IMAGE = Path(__file__).parent / "assets" / "connfas-network.jpg"
BACKEND_API_URL = os.getenv("CONNFAS_API_URL", "http://localhost:8000").rstrip("/")

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

        [data-testid="stForm"] {{
            background: rgba(5, 20, 36, 0.55);
            border: 1px solid rgba(185, 239, 255, 0.24);
            border-radius: 1rem;
            margin: 1.5rem auto 0;
            max-width: 34rem;
            padding: 1.25rem;
        }}

        [data-testid="stForm"] label {{
            color: #ffffff;
        }}

        .home-heading {{
            color: #ffffff;
            margin: 0 0 0.4rem;
        }}

        .home-heading h1 {{
            color: #ffffff;
        }}

        .home-description {{
            color: rgba(239, 248, 255, 0.82);
            margin: 0 0 1.5rem;
        }}

        .platform-name {{
            color: #ffffff;
            font-size: 1.2rem;
            font-weight: 700;
            margin: 0.5rem 0 0.25rem;
        }}

        .platform-description {{
            color: rgba(239, 248, 255, 0.75);
            font-size: 0.9rem;
            min-height: 2.8rem;
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

if st.session_state.get("otp_verified"):
    st.markdown(
        """
        <div class="home-heading">
            <div class="brand-kicker">Connfas workspace</div>
            <h1>Select a social platform</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="home-description">Choose a platform where you want to publish.</p>',
        unsafe_allow_html=True,
    )
    st.caption(f"Email verified: {st.session_state['otp_email']}")

    platforms = (
        ("Facebook", "f", "Connect a Facebook Page", True),
        ("Instagram", "◎", "Instagram account connection coming soon", False),
        ("X", "𝕏", "X account connection coming soon", False),
        ("LinkedIn", "in", "LinkedIn account connection coming soon", False),
        ("Pinterest", "P", "Pinterest account connection coming soon", False),
    )

    def render_platform(platform: tuple[str, str, str, bool], column) -> None:
        name, mark, description, available = platform
        with column:
            with st.container(border=True):
                st.markdown(
                    f'<div class="platform-name"><span aria-hidden="true">{mark}</span> &nbsp;{name}</div>'
                    f'<div class="platform-description">{description}</div>',
                    unsafe_allow_html=True,
                )
                selected = st.session_state.get("selected_platform") == name
                if st.button(
                    "Selected" if selected else f"Select {name}",
                    key=f"select_platform_{name}",
                    type="primary" if selected else "secondary",
                    use_container_width=True,
                    disabled=not available,
                ):
                    st.session_state["selected_platform"] = name

    first_row = st.columns(3, gap="medium")
    for platform, column in zip(platforms[:3], first_row):
        render_platform(platform, column)

    second_row = st.columns([0.5, 1, 1, 0.5], gap="medium")
    render_platform(platforms[3], second_row[1])
    render_platform(platforms[4], second_row[2])

    if st.session_state.get("selected_platform") == "Facebook":
        st.info(
            "Facebook is selected. Connecting a Facebook account and choosing a Page "
            "are not yet wired into this home page."
        )

    if st.button("Back to landing page"):
        for key in (
            "otp_email",
            "otp_verified",
            "existing_user",
            "selected_platform",
            "show_sign_in",
        ):
            st.session_state.pop(key, None)
        st.rerun()
else:
    sign_in_column, sign_up_column = st.columns(2, gap="medium")
    with sign_in_column:
        sign_in_clicked = st.button("Sign in", type="primary", use_container_width=True)
    with sign_up_column:
        sign_up_clicked = st.button("Sign up", type="secondary", use_container_width=True)

    if sign_in_clicked:
        st.session_state["show_sign_in"] = True
        st.session_state.pop("otp_email", None)
        st.session_state.pop("otp_verified", None)
    elif sign_up_clicked:
        st.session_state["show_sign_in"] = False

    if sign_up_clicked:
        st.info("Sign up is not connected yet.")

    if st.session_state.get("show_sign_in"):
        otp_email = st.session_state.get("otp_email")

        if otp_email is None:
            with st.form("request_email_otp_form"):
                email = st.text_input(
                    "Email address",
                    placeholder="Enter your email address",
                    autocomplete="email",
                )
                request_otp = st.form_submit_button(
                    "Send verification code",
                    type="primary",
                    use_container_width=True,
                )

            if request_otp:
                try:
                    response = httpx.post(
                        f"{BACKEND_API_URL}/auth/email/send-otp",
                        json={"email": email},
                        timeout=20,
                    )
                except httpx.RequestError:
                    st.error("Could not connect to Connfas. Check that the backend is running.")
                else:
                    if response.is_success:
                        st.session_state["otp_email"] = email.strip().lower()
                        st.session_state.pop("otp_verified", None)
                        st.success("If the address can receive email, a verification code has been sent.")
                        st.rerun()
                    else:
                        try:
                            detail = response.json().get("detail")
                        except ValueError:
                            detail = None
                        st.error(
                            detail
                            if isinstance(detail, str)
                            else f"Could not send a verification code (HTTP {response.status_code})."
                        )
        else:
            st.caption(f"Enter the verification code sent to {otp_email}.")
            with st.form("verify_email_otp_form"):
                code = st.text_input(
                    "Verification code",
                    placeholder="Enter the 6-digit code",
                    max_chars=6,
                    autocomplete="one-time-code",
                )
                verify_otp = st.form_submit_button(
                    "Verify email",
                    type="primary",
                    use_container_width=True,
                )

            if verify_otp:
                try:
                    response = httpx.post(
                        f"{BACKEND_API_URL}/auth/email/verify-otp",
                        json={"email": otp_email, "code": code},
                        timeout=20,
                    )
                except httpx.RequestError:
                    st.error("Could not connect to Connfas. Check that the backend is running.")
                else:
                    if response.is_success:
                        result = response.json()
                        st.session_state["otp_verified"] = result["verified"]
                        st.session_state["existing_user"] = result["existing_user"]
                        st.rerun()
                    else:
                        try:
                            detail = response.json().get("detail")
                        except ValueError:
                            detail = None
                        st.error(
                            detail
                            if isinstance(detail, str)
                            else f"Could not verify the code (HTTP {response.status_code})."
                        )

            resend_column, change_email_column = st.columns(2)
            with resend_column:
                resend_otp = st.button("Resend code", use_container_width=True)
            with change_email_column:
                change_email = st.button("Change email", use_container_width=True)

            if resend_otp:
                try:
                    response = httpx.post(
                        f"{BACKEND_API_URL}/auth/email/send-otp",
                        json={"email": otp_email},
                        timeout=20,
                    )
                except httpx.RequestError:
                    st.error("Could not connect to Connfas. Check that the backend is running.")
                else:
                    if response.is_success:
                        st.success("If the address can receive email, a verification code has been sent.")
                    else:
                        try:
                            detail = response.json().get("detail")
                        except ValueError:
                            detail = None
                        st.error(
                            detail
                            if isinstance(detail, str)
                            else f"Could not resend the code (HTTP {response.status_code})."
                        )

            if change_email:
                st.session_state.pop("otp_email", None)
                st.rerun()
