import Link from "next/link";

export default function DemoHome() {
  return <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 sm:py-16">
    <section className="rounded-3xl bg-emerald-950 p-7 text-white sm:p-12">
      <p className="text-xs font-semibold tracking-[0.2em] text-emerald-200">OSAKA MICHI-NO-EKI / INTERACTIVE DEMO</p>
      <h1 className="mt-6 text-3xl font-bold leading-snug sm:text-5xl sm:leading-tight">次の休み、<br />何駅まわれる？</h1>
      <p className="mt-6 max-w-xl text-base leading-8 text-emerald-100">大阪の実在する10駅から、小さな寄り道の計画を。<br className="hidden sm:block" />行きたい駅を選び、時間を変えて、無理のない順番を探します。</p>
      <div className="mt-8 flex flex-wrap gap-3"><Link href="/routes/new" className="rounded-xl bg-white px-6 py-3 font-bold text-emerald-950 hover:bg-emerald-100">3駅のサンプルで試す →</Link><Link href="/stations" className="rounded-xl border border-emerald-600 px-6 py-3 font-semibold hover:bg-emerald-900">10駅を見てみる</Link></div>
      <p className="mt-6 text-xs text-emerald-200">ログイン不要 · 実際のPythonロジックで再計算 · 入力の保存なし</p>
    </section>
    <section aria-label="体験できること" className="mt-8 grid gap-4 sm:grid-cols-3">
      {[
        ["01", "駅と順番を選ぶ", "大阪駅発の3駅プランから。駅の追加や並べ替えで、自分の行程に。", "/routes/new"],
        ["02", "遅れた場合を比べる", "30分遅れたら？ 滞在を延ばしたら？ 締切までの余裕を再計算。", "/routes/new"],
        ["03", "プランを提案してもらう", "効率や安全など、重みの異なる複数の候補を比較できます。", "/routes/suggest"],
      ].map(([number, title, text, href]) => <Link key={number} href={href} className="rounded-xl border border-zinc-200 bg-white p-6 transition-colors hover:border-emerald-700 dark:border-zinc-800 dark:bg-zinc-950"><span className="font-mono text-sm text-emerald-700 dark:text-emerald-400">{number}</span><h2 className="mt-3 font-bold">{title}</h2><p className="mt-3 text-sm leading-7 text-zinc-600 dark:text-zinc-400">{text}</p></Link>)}
    </section>
    <section className="mt-9 text-sm leading-7 text-zinc-600 dark:text-zinc-400"><h2 className="font-semibold text-zinc-900 dark:text-zinc-100">このデモについて</h2><p className="mt-2">駅名・住所・座標は、作成者が用意した近畿の簡易JSONから大阪府の10駅を抽出したものです。営業時間・スタンプ受付は全駅09:00〜17:00の仮値、休業日は未確認です。移動時間は座標からの概算で、交通状況や実際の道路を反映しません。</p><p className="mt-2">自動提案はルールと評価関数による計算です。出発前には各駅の案内と地図で最新情報をご確認ください。</p></section>
  </div>;
}
