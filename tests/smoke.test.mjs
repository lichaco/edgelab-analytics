import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const js=readFileSync(new URL('../assets/js/app.js',import.meta.url),'utf8');
const css=readFileSync(new URL('../assets/css/styles.css',import.meta.url),'utf8');

test('la pagina carga los assets locales versionados',()=>{
 assert.match(html,/href="assets\/css\/styles.css"/);
 assert.match(html,/src="assets\/js\/app.js"/);
 assert.ok(existsSync(new URL('../assets/js/app.js',import.meta.url)));
});
test('contiene cinco modulos y mercados esenciales',()=>{
 for(const name of ['football','basket','cs2','nhl','nfl']) assert.ok(js.includes(`id:'${name}'`),name);
 for(const name of ['corners','cards','rebounds','assists','threes']) assert.ok(js.includes(name),name);
});
test('tiene almacenamiento local y exportacion CSV y JSON',()=>{
 assert.match(js,/localStorage/);
 assert.match(js,/edgelab-analisis\.csv/);
 assert.match(js,/edgelab-analisis\.json/);
});
test('no contiene secrets obvios en el frontend',()=>{
 const combined=html+js+css;
 assert.doesNotMatch(combined,/DUNKAPI_API_KEY\s*[=:]\s*["']\w+/i);
 assert.doesNotMatch(combined,/sk-[A-Za-z0-9]{20,}/);
});
