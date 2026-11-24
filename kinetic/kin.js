// Rendert die Bilder eines Videos: node kin.js <job.json> <ausgabeordner>
// Hochformat (Standard): 1080x1920, 30 fps. Querformat (job.land): Bühne 1920x1080, gerendert mit job.zoom (z. B. 0.6667 = 1280x720), job.fps (z. B. 24).
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
(async()=>{
  const [inp,out]=process.argv.slice(2);const job=JSON.parse(fs.readFileSync(inp,'utf8'));fs.mkdirSync(out,{recursive:true});
  const land=!!job.land,zoom=job.zoom||1,fps=job.fps||30;
  const vw=land?Math.round(1920*zoom):1080,vh=land?Math.round(1080*zoom):1920;
  const b=await chromium.launch();const p=await b.newPage({viewport:{width:vw,height:vh},deviceScaleFactor:1});
  p.on('pageerror',e=>{console.log('Seitenfehler:',e.message);process.exitCode=2});
  await p.goto('file://'+path.resolve(__dirname,land?'stage_land.html':'stage.html'));
  await p.evaluate(j=>window.init(j),job);
  const n=Math.ceil(job.dur*fps);
  for(let i=0;i<n;i++){
    await p.evaluate(t=>window.frame(t),i/fps);
    await p.screenshot({path:path.join(out,'f'+String(i+1).padStart(5,'0')+'.jpg'),type:'jpeg',quality:land?80:84});
    if(i%1500===0)console.log(i+'/'+n);
  }
  console.log(n+' Bilder');await b.close();
})();
