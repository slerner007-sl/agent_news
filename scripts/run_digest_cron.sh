#!/usr/bin/env bash
set -euo pipefail

cd /home/user1/gosb_bot

if [ -f /home/user1/.config/gosb_bot.env ]; then
  set -a
  . /home/user1/.config/gosb_bot.env
  set +a
fi

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export NEWS_FILTER_VERSION="${NEWS_FILTER_VERSION:-v2}"
export NEWS_FILTER_MODE="${NEWS_FILTER_MODE:-live}"
export NEWS_V2_MAX_ITEMS="${NEWS_V2_MAX_ITEMS:-60}"
export NEWS_V2_DIGEST_LIMIT="${NEWS_V2_DIGEST_LIMIT:-0}"
export NEWS_V2_BATCH_SIZE="${NEWS_V2_BATCH_SIZE:-20}"
export TG_SEND_DELAY_SECONDS="${TG_SEND_DELAY_SECONDS:-1.5}"
export INSIGHTS_ENABLED="${INSIGHTS_ENABLED:-0}"
export PYTHONPATH="/home/user1/gosb_bot/src${PYTHONPATH:+:$PYTHONPATH}"

python3 -m agent_news.main
