import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const React = await import('react');
const { render, screen, fireEvent, cleanup, waitFor, act } = await import('@testing-library/react');
const { default: NewRoute } = await import('../src/app/routes/new/page.tsx');
const { default: SuggestRoute } = await import('../src/app/routes/suggest/page.tsx');
const { default: WhatIf } = await import('../src/app/routes/new/_components/WhatIfPanel.tsx');
const originalFetch = globalThis.fetch;
afterEach(() => { cleanup(); globalThis.fetch = originalFetch; });

const stations = [{ id: 1, name: 'テスト駅', pref: '大阪府', lat: 34.75, lon: 135.5,
  visited: false, stay_time_min_default: 15, business_hours: {}, closed_days: '' }];
const stop = { station_id: 1, name: 'テスト駅', arrival: '09:11', departure: '09:26',
  stay_min: 15, stamp_deadline: '17:00', margin_min: 469, warnings: [],
  latest_departure: null, departure_slack_min: null };
const result = { stops: [stop], totals: { travel_min: 11, distance_km: 7, stay_min: 15 },
  departure_time: '09:00', google_maps_url: 'https://example.com/route', warnings: [] };
const base = { origin: { lat: 34.7, lon: 135.5 }, departure_mode: 'fixed',
  departure_time: '09:00', station_ids: [1], stay_overrides: {}, return_to_origin: false,
  highway_legs: [], visit_date: null, auto_order: false };
const json = value => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });

async function manualSuccess() {
  globalThis.fetch = async url => json(String(url).endsWith('/stations') ? stations : result);
  render(React.createElement(NewRoute));
  fireEvent.click(await screen.findByRole('checkbox', { name: 'テスト駅大阪府' }));
  fireEvent.click(screen.getByRole('button', { name: 'プラン計算', exact: true }));
  await screen.findByRole('region', { name: 'プラン結果' });
}

test('手動: 成功後に全駅解除して送信すると古い結果とWhat-ifを取り下げる', async () => {
  await manualSuccess();
  fireEvent.click(screen.getByRole('button', { name: 'テスト駅を選択解除' }));
  fireEvent.click(screen.getByRole('button', { name: 'プラン計算', exact: true }));
  assert.ok(screen.getByText('訪問する道の駅を1駅以上選択してください。'));
  assert.ok(!screen.queryByRole('region', { name: 'プラン結果' }));
  assert.ok(!screen.queryByRole('region', { name: 'What-ifシミュレーション' }));
});

test('手動: 必須入力が空の送信でも古い結果を取り下げる', async () => {
  await manualSuccess();
  fireEvent.change(screen.getByRole('spinbutton', { name: '緯度' }), { target: { value: '' } });
  fireEvent.click(screen.getByRole('button', { name: 'プラン計算', exact: true }));
  assert.ok(!screen.queryByRole('region', { name: 'プラン結果' }));
});

test('自動: 通信失敗では古い提案を取り下げ、同じ条件で再試行できる', async () => {
  let offline = false;
  const suggested = { candidate_count: 1, warnings: [], plans: [{ ...result,
    key: 'efficiency', label: 'テスト提案', description: '', reason: '', finish_time: '09:26' }] };
  globalThis.fetch = async url => {
    if (String(url).endsWith('/stations')) return json(stations);
    if (offline) throw new TypeError('offline');
    return json(suggested);
  };
  render(React.createElement(SuggestRoute));
  await screen.findByRole('checkbox', { name: '大阪府' });
  fireEvent.click(screen.getByRole('button', { name: 'プランを提案', exact: true }));
  await screen.findByRole('heading', { name: 'テスト提案' });
  offline = true;
  fireEvent.change(screen.getByLabelText('出発時刻', { exact: true }), { target: { value: '10:00' } });
  fireEvent.click(screen.getByRole('button', { name: 'プランを提案', exact: true }));
  await screen.findByText(/に接続できません/);
  assert.ok(!screen.queryByRole('heading', { name: 'テスト提案' }));
  offline = false;
  fireEvent.click(screen.getByRole('button', { name: 'プランを提案', exact: true }));
  await screen.findByRole('heading', { name: 'テスト提案' });
  assert.ok(!screen.queryByText(/に接続できません/));
});

test('What-if: 条件変更直後と通信失敗時に古い結果・地図を取り下げる', async () => {
  let offline = false;
  globalThis.fetch = async () => {
    if (offline) throw new TypeError('offline');
    return json(result);
  };
  render(React.createElement(WhatIf, { baseRequest: base, baseStops: [stop] }));
  fireEvent.change(screen.getByRole('slider'), { target: { value: '30' } });
  await screen.findByRole('link', { name: 'この条件でGoogle Mapsを開く' });
  offline = true;
  fireEvent.change(screen.getByRole('slider'), { target: { value: '35' } });
  assert.ok(!screen.queryByRole('table'));
  await screen.findByText(/に接続できません/);
  assert.ok(!screen.queryByRole('link', { name: 'この条件でGoogle Mapsを開く' }));
});

test('What-if: 逆算プランの帰着締切を引き継いで再計算に含める', async () => {
  const bodies = [];
  globalThis.fetch = async (url, init) => { bodies.push(JSON.parse(init.body)); return json(result); };
  render(React.createElement(WhatIf, {
    baseRequest: { ...base, return_to_origin: true, return_by: '18:00' }, baseStops: [stop] }));
  const returnByInput = screen.getByLabelText('帰着締切（任意）');
  assert.equal(returnByInput.value, '18:00');
  fireEvent.change(screen.getByRole('slider'), { target: { value: '30' } });
  await waitFor(() => assert.equal(bodies.length, 1));
  assert.equal(bodies[0].return_by, '18:00');
  assert.equal(bodies[0].delay_min, 30);
});

test('What-if: リセット前に送った遅い応答は次の条件へ表示しない', async () => {
  const pending = [];
  globalThis.fetch = () => new Promise(resolve => pending.push(resolve));
  render(React.createElement(WhatIf, { baseRequest: base, baseStops: [stop] }));
  fireEvent.change(screen.getByRole('slider'), { target: { value: '30' } });
  await waitFor(() => assert.equal(pending.length, 1));
  fireEvent.click(screen.getByRole('button', { name: '元のプランに戻す' }));
  await act(async () => pending[0](json(result)));
  fireEvent.change(screen.getByRole('slider'), { target: { value: '60' } });
  assert.ok(!screen.queryByRole('table'));
  await waitFor(() => assert.equal(pending.length, 2));
  await act(async () => pending[1](json({ ...result, stops: [{ ...stop, arrival: '10:11' }] })));
  assert.ok(screen.getByRole('cell', { name: '10:11', exact: true }));
});

