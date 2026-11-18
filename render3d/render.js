// Rendert eine Szene Bild fuer Bild (Chromium ohne GPU): node render.js <szene> <px> <ausgabeordner> [nur-bild-zeit...]
const {chromium}=require('playwright'); const fs=require('fs');
(async()=>{
  const [scene,pxs,out,...stills]=process.argv.slice(2); const px=parseFloat(pxs||'1'), fps=30;
  fs.mkdirSync(out,{recursive:true});
  const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  const p=await b.newPage({viewport:{width:540,height:960},deviceScaleFactor:px});
  p.on('pageerror',e=>{console.log('Seitenfehler:',e.message);process.exitCode=2}); p.on('console',m=>{if(m.type()==='error')console.log('Konsole:',m.text())});
  await p.goto(`http://127.0.0.1:${process.env.PORT||8765}/stage.html?scene=${scene}&px=${px}`);
  await p.waitForFunction('window.ready===true',{timeout:120000});
  if(stills.length){for(const t of stills){await p.evaluate(t=>window.setTime(t),+t);await p.screenshot({path:`${out}/still_${t}.png`})};await b.close();return}
  const dur=await p.evaluate('window.duration'), n=Math.ceil(dur*fps), t0=Date.now();
  for(let i=0;i<n;i++){await p.evaluate(t=>window.setTime(t),i/fps);await p.screenshot({path:`${out}/f${String(i).padStart(5,'0')}.jpg`,type:'jpeg',quality:94});
    if(i%150===0)console.log(`Bild ${i}/${n} nach ${((Date.now()-t0)/1000).toFixed(0)} s`)}
  console.log(`${n} Bilder fertig, ${dur.toFixed(2)} s Video, ${((Date.now()-t0)/1000).toFixed(0)} s Rechenzeit`);await b.close();
})();
