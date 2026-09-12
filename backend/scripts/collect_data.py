"""データ収集一括実行スクリプト。XLSをマスターとしてGMLで座標・施設情報を補完する。"""
import argparse
import json
import sys
from pathlib import Path

# backend/ をimportパスに追加（app.data_pipeline を解決するため）
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.data_pipeline.collectors.kokudo_collector import collect as collect_gml
from app.data_pipeline.collectors.mlit_collector import load_xls, merge_with_gml


def main() -> None:
    parser = argparse.ArgumentParser(description="道の駅データ収集")
    parser.add_argument("--dry-run", action="store_true", help="実際には保存しない")
    args = parser.parse_args()

    # データはリポジトリルート直下の data/ に置く（docs/DESIGN.md 12章の決定）
    data_dir = Path(__file__).parent.parent.parent / "data" / "raw"
    xls_path = data_dir / "list.xls"

    if not xls_path.exists():
        print(f"エラー: {xls_path} が見つかりません")
        sys.exit(1)

    print("XLS読み込み中...")
    xls_stations = load_xls(xls_path)
    print(f"  XLS: {len(xls_stations)}件")

    print("GMLパース中...")
    gml_stations = collect_gml(data_dir)
    print(f"  GML: {len(gml_stations)}件")

    print("マージ中...")
    stations = merge_with_gml(xls_stations, gml_stations)
    gml_matched = sum(1 for s in stations if s["lat"] is not None)
    print(f"  マージ結果: {len(stations)}件（座標あり: {gml_matched}件、座標なし: {len(stations) - gml_matched}件）")

    if args.dry_run:
        print("\n[dry-run] 保存をスキップ — 先頭3件:")
        for s in stations[:3]:
            print(json.dumps(s, ensure_ascii=False, indent=2))
        return

    output_path = data_dir / "stations_kinki.json"
    output_path.write_text(
        json.dumps(stations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"保存完了 → {output_path}")


if __name__ == "__main__":
    main()
