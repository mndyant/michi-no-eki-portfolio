import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { PUBLIC_DEMO } from "@/lib/demo";

// ページ共通のメタ情報。タイトル・説明は日本語で設定する
export const metadata: Metadata = {
  title: "道の駅巡回計画",
  description:
    PUBLIC_DEMO ? "大阪の実在する10駅でルート作成・自動提案・遅延シミュレーションを体験できる公開デモ" : "近畿の道の駅スタンプラリーを、どこを・どの順で・何時に巡るか決める意思決定支援アプリ",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // lang="ja" を指定し、日本語ページであることを明示する
    <html lang="ja" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-zinc-50 text-zinc-900 dark:bg-black dark:text-zinc-50">
        {/* 全ページ共通ヘッダー。スマホでも読みやすいようにpaddingを調整 */}
        <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
            <Link href="/" className="text-lg font-semibold tracking-tight sm:text-xl">
              道の駅巡回計画
            </Link>
            {PUBLIC_DEMO && <nav aria-label="メインナビゲーション" className="flex gap-4 text-sm"><Link href="/stations">駅一覧</Link><Link href="/routes/new">ルート作成</Link><Link href="/routes/suggest">自動提案</Link></nav>}
          </div>
        </header>
        {PUBLIC_DEMO && <aside className="border-b border-amber-200 bg-amber-50 px-4 py-3 text-center text-xs leading-6 text-amber-950">公開デモ · 大阪府の実在10駅 ／ 営業・スタンプ受付09:00〜17:00は仮値・休業日未確認 ／ 移動時間は概算</aside>}

        {/* 各ページの内容。flex-1で余白を埋めてフッターを下部に固定する */}
        <main className="flex flex-1 flex-col">{children}</main>

        <footer className="border-t border-zinc-200 py-4 text-center text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
          {PUBLIC_DEMO ? <a href="https://github.com/mndyant/michi-no-eki-portfolio" target="_blank" rel="noopener noreferrer">大阪 道の駅巡回計画 · Portfolio demo · ソースコード ↗</a> : "近畿道の駅スタンプラリー巡回計画AI"}
        </footer>
      </body>
    </html>
  );
}
