// Rendert Szenen als PNG (1920x1080): node shots.js <shots.json> <ausgabeordner>
// shots.json: [{"name":"s001","spec":{...}}, ...]   (spec.type: titel, kapitel, zahl, liste, vergleich, zeitleiste, fakt, frage, vorschau)
const {chromium}=require('playwright'); const fs=require('fs'); const path=require('path');
(async()=>{
  const [inp,out]=process.argv.slice(2); const shots=JSON.parse(fs.readFileSync(inp,'utf8')); fs.mkdirSync(out,{recursive:true});
  const b=await chromium.launch(); const p=await b.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1});
  p.on('pageerror',e=>{console.log('Seitenfehler:',e.message);process.exitCode=2});
  await p.goto('file://'+path.resolve(__dirname,'stage.html'));
  for(const s of shots){await p.evaluate(sp=>window.show(sp),s.spec);await p.screenshot({path:path.join(out,s.name+'.png')})}
  console.log(shots.length+' Szenen gerendert');await b.close();
})();
