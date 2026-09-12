# frontend — 道の駅巡回計画

近畿道の駅スタンプラリー巡回計画AIのフロントエンド（Next.js App Router + TypeScript + Tailwind CSS）。

詳細な設計は [`docs/DESIGN.md`](../docs/DESIGN.md) を参照。

## セットアップ

```bash
npm install
cp .env.local.example .env.local  # 必要に応じて値を調整
npm run dev
```

[http://localhost:3000](http://localhost:3000) で確認できる。

## よく使うコマンド

```bash
npm run dev     # 開発サーバー起動
npm run build   # 本番ビルド
npm run lint    # ESLint実行
```
