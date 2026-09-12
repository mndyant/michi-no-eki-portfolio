import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/api.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
const api = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('FastAPIの422検証エラーを読めるメッセージにする', async (t) => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: [
    { loc: ['body', 'station_ids'], msg: 'List should have at least 1 item' },
  ] }), { status: 422 });
  await assert.rejects(api.fetchStations(), (error) =>
    error instanceof api.ApiError && error.status === 422 && error.message.includes('station_ids') && !error.message.includes('[object Object]'));
});

test('通信失敗は接続先を含む日本語メッセージを返す', async (t) => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async () => { throw new TypeError('offline'); };
  await assert.rejects(api.fetchStations(), /に接続できません/);
});
