import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timezone

async def fetch_analytics_summary(users_collection, chat_collection):
    df_users = pd.DataFrame(await users_collection.find({}, {"_id": 0, "chat_id": 1, "first_name": 1}).to_list(None))
    df_messages = pd.DataFrame(await chat_collection.find({}, {"_id": 0, "chat_id": 1, "sentiment": 1}).to_list(None))

    total_users = df_users.shape[0]
    total_messages = df_messages.shape[0]

    sentiment_counts = df_messages["sentiment"].value_counts().to_dict()
    sentiment_summary = "\n".join([f"🔹 {k}: {v}" for k, v in sentiment_counts.items()])

    summary = (
        f" **User Analytics Summary**\n\n"
        f" **Total Users**: {total_users}\n"
        f" **Total Messages**: {total_messages}\n\n"
        f" **Sentiment Analysis**:\n{sentiment_summary}"
    )
    return summary

async def generate_dashboard(users_collection, chat_collection):
    df_users = pd.DataFrame(await users_collection.find({}, {"_id": 0, "chat_id": 1, "first_name": 1}).to_list(None))
    df_messages = pd.DataFrame(
        await chat_collection.find({}, {"_id": 0, "chat_id": 1, "sentiment": 1, "timestamp": 1}).to_list(None))

    total_users = df_users.shape[0]
    total_messages = df_messages.shape[0]
    sentiment_counts = df_messages["sentiment"].value_counts()

    df_messages['timestamp'] = pd.to_datetime(df_messages['timestamp'])
    df_messages['date'] = df_messages['timestamp'].dt.date
    daily_counts = df_messages.groupby('date').size()
    top_users = df_messages['chat_id'].value_counts().head(5)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    sns.set(style="whitegrid")

    axes[0, 0].bar(['Users', 'Messages'], [total_users, total_messages], color=['blue', 'green'])
    axes[0, 0].set_title("Total Users & Messages")

    axes[0, 1].pie(sentiment_counts, labels=sentiment_counts.index, autopct='%1.1f%%', colors=sns.color_palette("pastel"))
    axes[0, 1].set_title("Sentiment Analysis")

    axes[1, 0].plot(daily_counts.index, daily_counts.values, marker='o', linestyle='-', color='purple')
    axes[1, 0].set_title("Messages Per Day")

    dashboard_path = "dashboard.png"
    plt.savefig(dashboard_path, dpi=100)
    plt.close()
    return dashboard_path
