import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {build} from '../node_modules/vite/dist/node/index.js';
import {mkdtempSync,readFileSync,readdirSync,rmSync} from 'node:fs';
import {join,resolve,basename,sep} from 'node:path';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=fileURLToPath(new URL('../',import.meta.url));
const scratch='D:/CodexScratch/tacticore-f05-configuration-gate-ui-20261029-v1';
const temporary=mkdtempSync(join(scratch,'component-'));
await build({root,base:'./',publicDir:false,build:{outDir:temporary,emptyOutDir:false,rollupOptions:{input:join(root,'component-tests/configuration-gate-parent-v1.html'),output:{inlineDynamicImports:true}}},logLevel:'error'});
const asset=readdirSync(join(temporary,'assets')).find(name=>name.endsWith('.js'));
const source=readFileSync(join(temporary,'assets',asset),'utf8');
let browser;
try{
 browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const context=await browser.newContext();const page=await context.newPage();
 page.setDefaultTimeout(7000);
 page.on('pageerror',error=>console.error('ARTIFICIAL_COMPONENT_ERROR',error.message));
 const check=()=>page.getByRole('button',{name:'检查对局',exact:true});
 const start=()=>page.getByRole('button',{name:'启动指挥官',exact:true});
 const arm=()=>page.getByRole('button',{name:'进入对局后自动启动',exact:true});
 const queryConfiguration=()=>page.getByRole('button',{name:'重新查询连接',exact:true});
 const recover=()=>page.getByRole('button',{name:'核对未完成的保存',exact:true});
 const banner=()=>page.locator('.native-notice');
 async function waitFor(value){await page.waitForFunction(value);}
 async function mount(search=''){
  await page.goto('about:blank');await page.setContent('<div id="root"></div>');
  await page.evaluate(value=>{window.fixtureSearch=value;},search);
  await page.addScriptTag({type:'module',content:source});
  await check().waitFor();
 }
 async function blocked(){assert.equal(await check().isDisabled(),true);assert.equal(await start().isDisabled(),true);assert.equal(await arm().isDisabled(),true);}
 async function ready(){await waitFor(()=>!document.querySelector('button')?.disabled&&[...document.querySelectorAll('button')].find(v=>v.textContent==='检查对局')?.disabled===false);}
 // Real parent + Panel: ordinary profile is loaded, but config query remains unresolved.
 await mount('?hold_configuration=1');
 await waitFor(()=>window.fakeCalls['profiles.list']===1&&typeof window.releaseConfiguration==='function');
 await blocked();assert.match(await banner().innerText(),/正在核对|尚未核验/);
 await page.evaluate(()=>window.releaseConfiguration());await ready();
 assert.equal(await start().isDisabled(),true);
 await check().click();await waitFor(()=>[...document.querySelectorAll('button')].find(v=>v.textContent==='启动指挥官')?.disabled===false);
 await page.evaluate(()=>window.setConfigurationMode('pending'));await queryConfiguration().click();await recover().waitFor();
 await blocked();assert.match(await banner().innerText(),/尚未完成核对/);
 assert.doesNotMatch(await banner().innerText(),/可发现游戏/);
 await recover().click();await ready();assert.equal(await start().isDisabled(),true);assert.equal(await page.getByRole('button',{name:'取消等待',exact:true}).count(),0);
 assert.equal((await page.evaluate(()=>window.fakeCalls))['run.start']??0,0);
 // Unknown query revokes a previously valid readiness; requery cannot restore its token.
 await check().click();await waitFor(()=>[...document.querySelectorAll('button')].find(v=>v.textContent==='启动指挥官')?.disabled===false);
 await page.evaluate(()=>window.setConfigurationMode('unknown'));await queryConfiguration().click();
 await page.getByRole('status').filter({hasText:'本机连接配置操作未完成'}).waitFor();await blocked();
 await page.evaluate(()=>window.setConfigurationMode('ready'));await queryConfiguration().click();await ready();assert.equal(await start().isDisabled(),true);
 // Already armed: a late positive check cannot start after pending -> ready.
 await page.evaluate(()=>window.holdRunCheck());await arm().click();await page.getByRole('button',{name:'取消等待',exact:true}).waitFor();
 await page.evaluate(()=>window.setConfigurationMode('pending'));await queryConfiguration().click();await recover().waitFor();
 await page.evaluate(()=>window.releaseRunCheck());await blocked();
 await recover().click();await ready();
 assert.equal(await start().isDisabled(),true);assert.equal(await page.getByRole('button',{name:'取消等待',exact:true}).count(),0);
 assert.equal((await page.evaluate(()=>window.fakeCalls))['run.start']??0,0);
 // Manual in-flight check also cannot republish old readiness after an error.
 await page.evaluate(()=>window.holdRunCheck());await check().click();
 await page.evaluate(()=>window.setConfigurationMode('unknown'));await queryConfiguration().click();
 await page.getByRole('status').filter({hasText:'本机连接配置操作未完成'}).waitFor();
 await page.evaluate(()=>window.releaseRunCheck());await blocked();
 await page.evaluate(()=>window.setConfigurationMode('ready'));await queryConfiguration().click();await ready();assert.equal(await start().isDisabled(),true);
 // Existing-run observation, STOP and diagnostics stay available despite pending configuration.
 await mount('?mode=pending&active_run=1');await recover().waitFor();
 for(const name of ['恢复观察已有宿主','查询运行状态','请求停止','下载脱敏诊断'])assert.equal(await page.getByRole('button',{name,exact:true}).isDisabled(),false,name);
 await page.getByRole('button',{name:'恢复观察已有宿主',exact:true}).click();
 await page.getByRole('button',{name:'查询运行状态',exact:true}).click();
 await page.getByRole('button',{name:'请求停止',exact:true}).click();
 await waitFor(()=>window.fakeCalls['run.stop']===1);
 assert.equal((await page.evaluate(()=>window.fakeCalls))['run.start']??0,0);
 // First-use text uses the current page; bootstrap reloads ordinary profile automatically.
 await mount('?first_use=1');await page.getByRole('button',{name:'初始化本机配置',exact:true}).waitFor();await blocked();
 assert.doesNotMatch(await page.getByRole('status').allTextContents().then(rows=>rows.join(' ')),/再重新打开客户端/);
 await page.getByRole('button',{name:'初始化本机配置',exact:true}).click();await ready();assert.equal(await start().isDisabled(),true);
 console.log(JSON.stringify({passed:true,parent_component_cases:6,actual_native_app_and_panel_mounted:true,fake_invokes_only:true,real_user_configuration_accessed:false,model_calls:0,game_access:false}));
 await context.close();
}finally{
 if(browser)await browser.close();
 if(resolve(temporary).startsWith(resolve(scratch)+sep)&&basename(temporary).startsWith('component-'))rmSync(temporary,{recursive:true,force:true});
}
