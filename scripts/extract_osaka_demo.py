"""Extract only the approved public station fields, without altering values."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
args = parser.parse_args()
raw_bytes = args.source.read_bytes()
raw = json.loads(raw_bytes.decode("utf-8-sig"))
fields = ("station_id", "name", "pref", "address", "url", "registration", "reg_date", "lat", "lon", "facilities")
rows = [{key: station[key] for key in fields if key in station} for station in raw if station.get("pref") == "大阪府"]
assert len(rows) == 10 and all(s.get("lat") is not None and s.get("lon") is not None for s in rows)
out = Path(__file__).resolve().parents[1] / "data/demo"
out.mkdir(parents=True, exist_ok=True)
(out / "stations_osaka.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(out / "provenance.json").write_text(json.dumps({
    "source_filename": args.source.name,
    "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
    "selection": "pref == 大阪府",
    "station_count": len(rows),
    "description": "作成者提供の簡易JSONから、本人の指示に基づいて大阪府の公開駅情報のみ抽出。値は変更していません。",
    "limitations": "営業時間・スタンプ受付・休業日・現在の営業状況は未確認。抽出日を確認日とは扱いません。"
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Extracted {len(rows)} Osaka stations")
