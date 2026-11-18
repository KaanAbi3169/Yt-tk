const {chromium}=require('playwright'); const fs=require('fs');
(async()=>{
  const fps=30, dur=parseFloat(process.argv[2]||'4'), px=parseFloat(process.argv[3]||'1');
  fs.rmSync('frames',{recursive:true,force:true}); fs.mkdirSync('frames');
  const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  const p=await b.newPage({viewport:{width:540,height:960},deviceScaleFactor:px});
  await p.goto('http://127.0.0.1:8765/scene.html?px='+px); await p.waitForFunction('window.ready===true',{timeout:60000});
  const n=Math.round(fps*dur), t0=Date.now();
  for(let i=0;i<n;i++){ await p.evaluate(t=>window.setTime(t),i/fps); await p.screenshot({path:`frames/f${String(i).padStart(4,'0')}.png`}); }
  console.log(n,'Bilder in',((Date.now()-t0)/1000).toFixed(1),'s'); await b.close();
})();
