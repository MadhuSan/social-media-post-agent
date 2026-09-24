from managed_deepagents import define_schedule

PROMPT = "Run the daily post draft. Follow the draft-posts skill."

schedule = define_schedule(
    # 9:00am IST, Monday-Friday
    cron="0 9 * * 1-5",
    timezone="Indian Standard Time",
    prompt=PROMPT,
    deliver_to={
        "channel": "slack",
        "to": {
            "type": "provider_conversation",
            "conversation_id": "******",
        },
        "auto_post": False,
    },
)