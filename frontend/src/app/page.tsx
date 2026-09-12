import Link from "next/link";

// トップページ
// アプリの目的（巡回計画の意思決定支援）を簡潔に説明し、
// 「道の駅一覧」「ルート作成」への導線を提供する。
// フェーズ2で追加した「ルート作成」画面への導線も提供する。
export default function Home() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-4 py-10 sm:px-6 sm:py-16">
      <section className="flex flex-col gap-3">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          道の駅巡回計画へようこそ
        </h1>
        <p className="leading-7 text-zinc-600 dark:text-zinc-300">
          近畿7府県（大阪・京都・兵庫・奈良・和歌山・滋賀・福井）の道の駅スタンプラリーを
          「どこを・どの順で・何時に巡るか」決めるための意思決定支援アプリです。
          営業時間やスタンプ受付終了時刻を考慮しながら、現実的に回れるプランを検討できます。
          最終的なカーナビはGoogleマップに委譲し、本アプリは巡回計画の検討に特化しています。
        </p>
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* 道の駅一覧への導線 */}
        <Link
          href="/stations"
          className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-5 shadow-sm transition-colors hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-600"
        >
          <h2 className="text-lg font-semibold">道の駅一覧</h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            訪問済み・未訪問の管理や、営業時間・滞在時間の確認ができます。
          </p>
        </Link>

        {/* ルート作成への導線 */}
        <Link
          href="/routes/new"
          className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-5 shadow-sm transition-colors hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-600"
        >
          <h2 className="text-lg font-semibold">ルート作成</h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            複数の道の駅を選び、訪問順どおりの時刻表とGoogle Mapsリンクを作成できます。
          </p>
        </Link>

        {/* 自動ルート提案への導線（フェーズ3） */}
        <Link
          href="/routes/suggest"
          className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-5 shadow-sm transition-colors hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-600"
        >
          <h2 className="text-lg font-semibold">自動ルート提案</h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            出発条件を入れると、効率重視・安全重視など狙いの異なるプランを自動で組み立てます。
          </p>
        </Link>
      </section>
    </div>
  );
}
