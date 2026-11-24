// Rendert die Bilder eines Kurzvideos (1080x1920, 30 fps): node kin.js <job.json> <ausgabeordner>
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
(async()=>{
  const [inp,out]=process.argv.slice(2);const job=JSON.parse(fs.readFileSync(inp,'utf8'));fs.mkdirSync(out,{recursive:true});
  const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
  p.on('pageerror',e=>{console.log('Seitenfehler:',e.message);process.exitCode=2});
  await p.goto('file://'+path.resolve(__dirname,'stage.html'));
  await p.evaluate(j=>window.init(j),job);
  const n=Math.ceil(job.dur*30);
  for(let i=0;i<n;i++){
    await p.evaluate(t=>window.frame(t),i/30);
    await p.screenshot({path:path.join(out,'f'+String(i+1).padStart(5,'0')+'.jpg'),type:'jpeg',quality:84});
  }
  console.log(n+' Bilder');await b.close();
})();
