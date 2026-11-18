// T001: Mythos "Wir nutzen nur 10 Prozent des Gehirns" (eigene Szene, nur Stil der Referenzvideos)
export default function(S){
  const {THREE,scene,cam,mat,add,textPlane,ease,clamp,lerp,pop,T,TE,D,makeFigure}=S;
  scene.background=new THREE.Color(0x1d2a5b); scene.fog=new THREE.Fog(0x1d2a5b,16,34);
  add(new THREE.BoxGeometry(20,0.2,20),mat(0x2b3c7d),0,-0.1,0);
  add(new THREE.CylinderGeometry(2.6,2.8,0.25,40),mat(0x3d55b3),0,0.12,0);                       // Podest
  const fig=makeFigure({headScale:1.75});
  // Gehirn: 10 Bereiche (Kugeln) im Kopf
  const lobes=[],cols=[];
  for(let i=0;i<10;i++){
    const y=1-(i+0.5)/10*1.6, r=Math.sqrt(Math.max(0,1-y*y)), a=i*2.399963;
    const m=new THREE.MeshStandardMaterial({color:0x666b7a,emissive:0x000000,roughness:0.5,flatShading:true});
    const o=add(new THREE.SphereGeometry(0.2,12,10),m,Math.cos(a)*r*0.36,y*0.36,Math.sin(a)*r*0.36,fig.head); o.castShadow=false;
    lobes.push(o);cols.push(new THREE.Color().setHSL(i/10,0.85,0.55));
  }
  fig.skull.material=mat(0xf2b88a,0.6,{transparent:true,opacity:0.32,depthWrite:false});
  fig.group.position.set(0,0.75,0); fig.group.scale.setScalar(1.0);
  // Texte
  const t10=textPlane('10 %',{w:2.6,h:1.1,color:'#ffd24a',size:330,stroke:'#12183a'});t10.position.set(0,5.3,0.5);scene.add(t10);
  const stamp=textPlane('MYTHOS',{w:3.4,h:1.0,color:'#fff',bg:'#e0262b',size:210,radius:50});stamp.position.set(0,5.3,0.8);stamp.rotation.z=-0.14;scene.add(stamp);
  const lblG=textPlane('Gewicht 2–3 %',{w:1.6,h:0.6,color:'#fff',size:120});lblG.position.set(-1.0,5.3,0.5);scene.add(lblG);
  const lblE=textPlane('Energie ~20 %',{w:1.6,h:0.6,color:'#ffd24a',size:120});lblE.position.set(1.0,5.3,0.5);scene.add(lblE);
  const barG=add(new THREE.BoxGeometry(0.5,1,0.4),mat(0x6fc7ff),-1.45,3.0,0),barE=add(new THREE.BoxGeometry(0.5,1,0.4),mat(0xffb020),1.45,3.0,0);
  const out=textPlane('Ausfall!',{w:2.4,h:0.9,color:'#fff',bg:'#e0262b',size:200,radius:40});out.position.set(0,5.3,0.8);scene.add(out);
  const ring=add(new THREE.TorusGeometry(1.5,0.05,8,48),new THREE.MeshBasicMaterial({color:0x7be3ff,transparent:true,opacity:0.9}),0,3.4,0);ring.rotation.x=Math.PI/2;ring.castShadow=false;
  const keep=textPlane('Nicht überall gleich stark',{w:3.6,h:0.8,color:'#fff',size:120,stroke:'#12183a'});keep.position.set(0,5.3,0.6);scene.add(keep);
  // Zeitmarken aus der Sprache (mit Reserve, falls ein Wort nicht erkannt wurde)
  const tZehn=T(/^zehn$/,0,0.6), tMyth=T(/mythos/,0,D*0.1), tScan=T(/hirnscans/,0,D*0.16), tAktiv=TE(/aktiv/,0,D*0.3), tWiegt=T(/wiegt/,0,D*0.34),
        tEner=TE(/energie/,0,D*0.5), tSchl=T(/schlaganfall/,0,D*0.56), tSofort=TE(/sofort/,0,D*0.66), tMiss=T(/missverst/,0,D*0.7), tAlles=T(/^also$/,0,D*0.82);
  const show=(o,v)=>{o.visible=v>0.001;o.scale.setScalar(Math.max(v,0.0001))};
  return {update(t){
    // Bereiche: erst nur einer, dann Scan, Ausfall eines Bereichs, am Ende alle (unterschiedlich stark)
    const scanP=clamp((t-tScan)/Math.max(0.5,tAktiv-tScan));
    lobes.forEach((o,i)=>{
      let lit = i===0?1:0;
      if(t>=tScan) lit=Math.max(lit, clamp(scanP*10-i,0,1));
      if(t>=tSchl&&t<tMiss&&i===3) lit = (Math.floor(t*10)%2?0.9:0.1)*(t<tSchl+1.2?1:0)||0.05;
      if(t>=tAlles) lit=0.55+0.45*Math.sin(t*(2.2+i*0.35)+i);
      const c=cols[i];o.material.emissive.copy(c).multiplyScalar(lit*0.9);o.material.color.copy(c).lerp(new THREE.Color(0x666b7a),1-lit);
    });
    // Kopf und Arme
    fig.head.rotation.y=Math.sin(t*1.2)*0.25; fig.head.rotation.z=(t>=tSchl&&t<tMiss)?Math.sin(t*14)*0.05:0;
    fig.armR.rotation.z=lerp(0.25,-2.2,clamp((t-tZehn)/0.5))*(t<tAlles?1:0)+(t>=tAlles?-2.6+Math.sin(t*6)*0.2:0); fig.armL.rotation.z=0.25;
    fig.group.position.y=0.25+(t>=tAlles?Math.abs(Math.sin(t*3))*0.12:0);
    // Overlays
    show(t10, t>=tZehn&&t<tScan? pop((t-tZehn)/0.4):0); t10.rotation.z=Math.sin(t*2)*0.03;
    show(stamp, t>=tMyth&&t<tScan? pop((t-tMyth)/0.35):0);
    ring.visible=t>=tScan&&t<tAktiv; ring.position.y=lerp(4.9,2.4,(scanP*3)%1);
    const bp=clamp((t-tWiegt)/0.8), be=clamp((t-tWiegt-0.4)/Math.max(0.6,tEner-tWiegt-0.4));
    const on=t>=tWiegt&&t<tSchl;
    [barG,barE,lblG,lblE].forEach(o=>o.visible=on);
    barG.scale.y=Math.max(0.01,0.35*ease(bp)); barG.position.y=2.9+barG.scale.y/2;
    barE.scale.y=Math.max(0.01,2.0*ease(be)); barE.position.y=2.9+barE.scale.y/2;
    show(out, t>=tSchl&&t<tMiss? pop((t-tSchl)/0.3):0);
    show(keep, t>=tAlles? pop((t-tAlles)/0.5):0);
    // Kamera
    const a=ease(clamp(t/D));
    cam.position.set(Math.sin(t*0.35)*0.6, lerp(3.5,3.3,a), lerp(8.2,7.0,a));
    cam.lookAt(0,3.5,0);
  }}
}
