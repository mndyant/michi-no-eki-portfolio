from scripts.seed_demo import demo_rows


def test_demo_rows_are_explicitly_fictional_and_unvisited():
    rows, clusters = demo_rows()
    assert len(rows) == 8 and clusters
    assert len({row["station_id"] for row in rows}) == 8
    assert all(row["name"].startswith("デモ") and "架空" in row["source"] for row in rows)
    assert all(not row["visited"] and row["official_url"] is None for row in rows)
