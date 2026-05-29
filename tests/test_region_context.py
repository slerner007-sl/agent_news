from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_news.region_context import get_region_context_for_gosb
from agent_news.sources_loader import load_sources


samara = get_region_context_for_gosb(
    {"name": "Самарский ГОСБ", "region": "Самарская область", "keywords": '["самара"]'},
    max_chars=1600,
)
kaliningrad = get_region_context_for_gosb(
    {"name": "Калининградский ГОСБ", "region": "Калининградская область", "keywords": "[]"},
    max_chars=1600,
)
ulyanovsk = get_region_context_for_gosb(
    {"name": "Ульяновский ГОСБ", "region": "Ульяновская область", "keywords": "[]"},
    max_chars=1600,
)

assert "Самарская область" in samara
assert "продажи новостроек" in samara
assert "Калининградская область" in kaliningrad
assert "рост налоговой нагрузки" in kaliningrad
assert "Ульяновская область" in ulyanovsk
assert "Активность ТСТ" in ulyanovsk

rss_sources, tg_sources, wpapi_sources = load_sources()
rss_names = {item["name"] for item in rss_sources}
tg_names = {item["name"] for item in tg_sources}

assert "KaliningradToday" in rss_names
assert "Калининград ТВ" in rss_names
assert "УлПравда" in rss_names
assert "Ульяновск Экспресс" in rss_names
assert "РБК Недвижимость" in tg_names
assert "РИА Недвижимость" in tg_names
assert not wpapi_sources

print("region context ok")
