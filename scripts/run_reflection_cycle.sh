#!/usr/bin/env bash
set -euo pipefail

cd /home/user1/gosb_bot

if [ -f /home/user1/.config/gosb_bot.env ]; then
  set -a
  . /home/user1/.config/gosb_bot.env
  set +a
fi

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export PYTHONPATH="/home/user1/gosb_bot/src${PYTHONPATH:+:$PYTHONPATH}"

cycle="${1:-weekly}"
send_flag=()
if [ "${REFLECTION_REPORT_SEND:-1}" = "1" ]; then
  send_flag=(--send)
fi

python3 -m agent_news.reflection_cycles --cycle "$cycle" "${send_flag[@]}"
