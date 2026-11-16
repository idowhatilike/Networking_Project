const fs = require('node:fs') ;
const path = require('node:path') ;
const os = require('node:os') ;
const http = require('node:http') ;
const { spawn } = require('node:child_process') ;

const projectRoot = path.resolve(__dirname , '..') ;
const phase = process.argv[2] || 'all' ;
const chromePath = process.env.OGK_TEST_CHROME ||
  'C:/Program Files/Google/Chrome/Application/chrome.exe' ;
const tempDir = fs.mkdtempSync(path.join(os.tmpdir() , 'ogk-browser-')) ;
const requests = {} ;
const apiPortServer = http.createServer() ;

function listen(server) {
  return new Promise(resolve => server.listen(0 , '127.0.0.1' , resolve)) ;
}

function close(server) {
  return new Promise(resolve => server.close(resolve)) ;
}

async function main() {
  await listen(apiPortServer) ;
  const apiPort = apiPortServer.address().port ;
  await close(apiPortServer) ;
  const serverCode = [
    'import server,uvicorn' ,
    'from agent.ui import issueBootstrapTicket' ,
    "issueBootstrapTicket('browser-regression-only')" ,
    `uvicorn.run(server.app,host='127.0.0.1',port=${apiPort},log_level='error')`
  ].join(';') ;
  const api = spawn(path.join(projectRoot , '.venv/Scripts/python.exe') ,
    ['-B' , '-c' , serverCode] , {
      cwd : tempDir , windowsHide : true ,
      env : { ...process.env , PYTHONPATH : projectRoot } , stdio : 'ignore'
    }) ;
  let chrome ;
  const proxy = http.createServer(async (req , res) => {
    const url = new URL(req.url , 'http://localhost') ;
    requests[url.pathname] = (requests[url.pathname] || 0) + 1 ;
    if (url.pathname === '/__review__/metrics') {
      res.end(JSON.stringify(requests)) ;
      return ;
    }
    if (url.pathname.startsWith('/__review__/error/')) {
      res.writeHead(Number(url.pathname.split('/').pop())) ;
      res.end('Lỗi kiểm chứng') ;
      return ;
    }
    if (url.pathname === '/__review__/offline') {
      res.destroy() ;
      return ;
    }
    if (url.pathname === '/__review__') {
      res.setHeader('Content-Type' , 'text/html; charset=utf-8') ;
      res.end(browserPage()) ;
      return ;
    }
    try {
      const chunks = [] ;
      for await (const chunk of req) chunks.push(chunk) ;
      const upstream = await fetch(`http://127.0.0.1:${apiPort}${req.url}` , {
        method : req.method , headers : req.headers , redirect : 'manual' ,
        body : chunks.length ? Buffer.concat(chunks) : undefined
      }) ;
      let body = Buffer.from(await upstream.arrayBuffer()) ;
      const headers = Object.fromEntries(upstream.headers) ;
      delete headers['content-length'] ;
      if ((headers['content-type'] || '').includes('text/html')) {
        body = Buffer.from(body.toString().replaceAll('every 30s' , 'every 0.1s')
          .replaceAll('every 3s' , 'every 0.1s')) ;
      }
      if (url.pathname === '/static/vendor/chart.umd.min.js') {
        body = Buffer.concat([body , Buffer.from(`
          window.chartCreates = 0; window.chartDestroys = 0;
          const originalChart = window.Chart;
          const destroyChart = originalChart.prototype.destroy;
          originalChart.prototype.destroy = function(...args) {
            window.chartDestroys++; return destroyChart.apply(this,args);
          };
          window.Chart = new Proxy(originalChart,{construct(target,args) {
            window.chartCreates++; return Reflect.construct(target,args);
          }});
        `)]) ;
      }
      res.writeHead(upstream.status , headers) ;
      res.end(body) ;
    } catch (error) {
      res.writeHead(502) ;
      res.end(String(error)) ;
    }
  }) ;
  try {
    for (let attempt = 0 ; ; attempt++) {
      try {
        await fetch(`http://127.0.0.1:${apiPort}/login`) ;
        break ;
      } catch (error) {
        if (attempt >= 100) throw error ;
        await new Promise(resolve => setTimeout(resolve , 50)) ;
      }
    }
    await listen(proxy) ;
    const args = [
      '--headless=new' , '--disable-gpu' , '--no-first-run' ,
      '--disable-background-networking' , '--disable-component-update' , '--disable-sync' ,
      '--no-default-browser-check' , `--user-data-dir=${path.join(tempDir , 'profile')}` ,
      '--dump-dom' , '--virtual-time-budget=60000' ,
      `http://127.0.0.1:${proxy.address().port}/__review__`
    ] ;
    chrome = spawn(chromePath , args , {
      windowsHide : true , stdio : ['ignore' , 'pipe' , 'ignore']
    }) ;
    let output = '' ;
    chrome.stdout.on('data' , chunk => { output += chunk ; }) ;
    const timeout = setTimeout(() => chrome.kill() , 30000) ;
    await new Promise(resolve => chrome.once('exit' , resolve)) ;
    clearTimeout(timeout) ;
    const report = output.match(/<pre id="result">([\s\S]*?)<\/pre>/)?.[1] ;
    if (!report) throw new Error('Trình duyệt không trả kết quả kiểm chứng.') ;
    console.log(report) ;
    const results = JSON.parse(report) ;
    if (!results.length || results.some(result => result.error)) process.exitCode = 1 ;
  } finally {
    chrome?.kill() ;
    proxy.closeAllConnections() ;
    await close(proxy) ;
    api.kill() ;
  }
}

function browserPage() {
  return `<!DOCTYPE html><meta charset="utf-8"><iframe id="page"></iframe>
  <pre id="result"></pre><script>
  const phase = ${JSON.stringify(phase)};
  const frame = document.getElementById('page');
  const results = [];
  const sleep = ms => new Promise(resolve => setTimeout(resolve,ms));
  const assert = (value,message) => { if (!value) throw Error(message); };
  async function waitFor(check) {
    for (let n=0;n<60;n++) { if (await check()) return; await sleep(50); }
    throw Error('Hết thời gian chờ kết quả.');
  }
  async function openPage(url) {
    await new Promise(resolve => {frame.onload=resolve;frame.src=url});
    return frame.contentDocument;
  }
  async function test(name,run) {
    try {await run();results.push({name,pass:true})}
    catch(error) {results.push({name,error:error.message})}
  }
  async function metrics() {return (await fetch('/__review__/metrics')).json()}
  (async()=>{
    if (phase==='step2' || phase==='all') {
      await test('clear_invalid_form',async()=>{
        const doc=await openPage('/children/child-bi/limits');
        doc.querySelector('[name=weekday_quota_min]').value='';
        let submitted=false;
        doc.querySelector('form[action$="/limits"]').addEventListener('submit',()=>{
          submitted=true;
        });
        const loaded=new Promise(resolve=>{frame.onload=resolve});
        doc.querySelector('[value=clear_adjustments]').click();
        assert(submitted,'Nút xóa bị chặn bởi kiểm tra form.');
        await loaded;
        assert(frame.contentDocument.body.textContent.includes('Đã xóa sạch điều chỉnh'),
          'Server chưa xác nhận xóa điều chỉnh.');
      });
      await test('retain_invalid_input',async()=>{
        const response=await fetch('/children/child-bi/limits',{method:'POST',
          body:new URLSearchParams({weekday_quota_min:'abc',weekend_quota_min:'12',
            budget_gaming:'3',budget_entertainment:'4',budget_education:'5'})});
        assert(response.status===422,'Thiếu mã lỗi 422.');
        await new Promise(async resolve=>{
          frame.onload=resolve;frame.srcdoc=await response.text();
        });
        assert(frame.contentDocument.querySelector('[name=weekday_quota_min]').value==='abc',
          'Trình duyệt đã xóa giá trị sai.');
        frame.removeAttribute('srcdoc');
      });
    }
    if (phase==='step3' || phase==='all') {
      await test('domain_get_form',async()=>{
        const doc=await openPage('/children/child-bi/web');
        doc.querySelector('[name=name]').value='roblox.com';
        doc.querySelector('form[hx-get="/domains/check"] button').click();
        await waitFor(()=>doc.querySelector('#domain-check-result code')?.textContent
          ==='roblox.com');
      });
      await test('replace_table_row',async()=>{
        const doc=await openPage('/requests');
        const form=doc.querySelector('form[hx-post]');
        const id=form.closest('tr').id;
        form.querySelector('[name=message]').value='Đồng ý cho con';
        form.querySelector('[value=approve]').click();
        await waitFor(()=>doc.getElementById(id).textContent.includes('Đã đồng ý'));
      });
      await test('repeat_card_poll',async()=>{
        const doc=await openPage('/');
        const url=doc.querySelector('article[hx-get]').getAttribute('hx-get');
        const before=(await metrics())[url]||0;
        await waitFor(async()=>((await metrics())[url]||0)>=before+3);
      });
      await openPage('/auth/bootstrap?ticket=browser-regression-only');
      await test('repeat_request_poll',async()=>{
        const doc=await openPage('/kid/requests');
        const oldRow=doc.querySelector('tr[hx-get]');
        const url=oldRow.getAttribute('hx-get');
        const before=(await metrics())[url]||0;
        await waitFor(async()=>((await metrics())[url]||0)>=before+3);
        assert(!doc.body.contains(oldRow),'Dòng yêu cầu không được thay vào bảng.');
      });
      for (const status of [401,403,404,422,500,'offline']) {
        await test('error_'+status,async()=>{
          const doc=frame.contentDocument;
          const button=doc.createElement('button');
          const area=doc.getElementById('toast-area');
          area.textContent='';
          button.setAttribute('hx-get',status==='offline'?'/__review__/offline':
            '/__review__/error/'+status);
          doc.body.appendChild(button);frame.contentWindow.htmx.process(button);button.click();
          await waitFor(()=>area.textContent.trim().length>0);
          assert(!area.querySelector('script'),'Thông báo lỗi chứa script.');
        });
      }
    }
    if (phase==='step4' || phase==='all') {
      if (phase!=='all') await openPage('/auth/bootstrap?ticket=browser-regression-only');
      for (const url of ['/children/child-bi/reports','/kid/report']) {
        await test('chart_'+url,async()=>{
          const doc=await openPage(url);
          const win=frame.contentWindow;
          const canvas=doc.querySelector('canvas');
          await waitFor(()=>canvas.getContext('2d')
            .getImageData(0,0,canvas.width,canvas.height).data.some(value=>value!==0));
          assert(win.chartCreates===1 && win.chartDestroys===0,'Biểu đồ khởi tạo/hủy thừa.');
          assert(doc.querySelector('details').open,'Bảng số liệu chưa mở sẵn.');
          const unrelated=doc.createElement('div');
          unrelated.id='unrelated';doc.body.appendChild(unrelated);
          win.htmx.swap(unrelated,'<div id="unrelated">Updated</div>',{swapStyle:'outerHTML'});
          await sleep(50);
          assert(win.chartCreates===1,'Thay vùng khác vẫn khởi tạo lại biểu đồ.');
          win.htmx.swap(canvas,canvas.outerHTML,{swapStyle:'outerHTML'});
          await waitFor(()=>win.chartCreates===2);
          assert(win.chartDestroys===1,'Biểu đồ cũ không được hủy khi thay canvas.');
        });
      }
    }
    document.getElementById('result').textContent=JSON.stringify(results);
  })();
  </script>` ;
}

main().catch(error => { console.error(error.message) ; process.exitCode = 1 ; }) ;
