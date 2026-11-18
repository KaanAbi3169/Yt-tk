// G001: "Heute erscheint GTA 6" (Nachricht mit belegten Fakten; nur eigene Grafik, keine Logos, kein Spielmaterial)
export default function(S){
  const {THREE,scene,cam,mat,add,textPlane,ease,clamp,lerp,pop,T,TE,D,makeFigure}=S;
  scene.background=new THREE.Color(0xff7a5a); scene.fog=new THREE.Fog(0xff7a5a,18,40);
  // Himmel-Verlauf und Sonne
  const sky=new THREE.Mesh(new THREE.PlaneGeometry(40,24),new THREE.MeshBasicMaterial({vertexColors:true}));
  const col=sky.geometry.attributes.position.count,cs=[];for(let i=0;i<col;i++){const y=sky.geometry.attributes.position.getY(i);const k=(y+12)/24;const c=new THREE.Color(0x3a1f7a).lerp(new THREE.Color(0xff8a4a),1-k);cs.push(c.r,c.g,c.b)}
  sky.geometry.setAttribute('color',new THREE.Float32BufferAttribute(cs,3));sky.position.set(0,9,-14);scene.add(sky);
  const sunD=new THREE.Mesh(new THREE.CircleGeometry(3.2,40),new THREE.MeshBasicMaterial({color:0xffd24a}));sunD.position.set(0,5.2,-13.5);scene.add(sunD);
  add(new THREE.BoxGeometry(30,0.2,30),mat(0x241446),0,-0.1,-4);
  for(let i=-6;i<=6;i++){add(new THREE.BoxGeometry(0.05,0.02,30),new THREE.MeshBasicMaterial({color:0xff4fa0}),i*1.5,0.02,-4).castShadow=false}
  // Kalender
  const cal=new THREE.Group();cal.position.set(0,4.5,0);cal.scale.setScalar(0.95);scene.add(cal);
  add(new THREE.BoxGeometry(2.8,3.3,0.35),mat(0xffffff),0,0,0,cal);
  add(new THREE.BoxGeometry(2.8,0.8,0.4),mat(0xe0262b),0,1.25,0.02,cal);
  const mon=textPlane('NOV 2026',{w:2.4,h:0.6,color:'#fff',size:150});mon.position.set(0,1.25,0.25);cal.add(mon);
  const d19=textPlane('19',{w:2.4,h:1.9,color:'#1b1b33',size:700});d19.position.set(0,-0.35,0.2);cal.add(d19);
  const pageG=new THREE.Group();pageG.position.set(0,1.65,0.25);cal.add(pageG);                      // Blatt "18", klappt weg
  const p18=add(new THREE.BoxGeometry(2.7,2.9,0.05),mat(0xfafafa),0,-1.45,0,pageG);
  const d18=textPlane('18',{w:2.4,h:1.9,color:'#1b1b33',size:700});d18.position.set(0,-1.55,0.05);pageG.add(d18);
  for(const x of[-0.8,0,0.8]) add(new THREE.CylinderGeometry(0.07,0.07,0.5,8),mat(0x333344),x,1.65,0.2,cal).rotation.z=Math.PI/2;
  const fig=makeFigure({});fig.group.position.set(-1.0,0,1.6);fig.group.rotation.y=0.45;fig.group.scale.setScalar(0.7);
  // Konsole (allgemein), PC mit Fragezeichen, Geruechte-Blasen
  const con=new THREE.Group();con.position.set(0.95,3.65,1.5);con.scale.setScalar(0.55);scene.add(con);
  add(new THREE.BoxGeometry(0.5,1.6,1.3),mat(0xf3f3f7),0,0,0,con);add(new THREE.BoxGeometry(0.52,1.5,0.18),mat(0x15151f),0,0,0.2,con);
  const pc=new THREE.Group();pc.position.set(-0.95,3.45,1.5);pc.scale.setScalar(0.6);scene.add(pc);
  add(new THREE.BoxGeometry(1.9,1.2,0.12),mat(0x222233),0,0.9,0,pc);add(new THREE.BoxGeometry(0.15,0.6,0.15),mat(0x222233),0,0.25,0,pc);add(new THREE.BoxGeometry(0.9,0.06,0.5),mat(0x222233),0,-0.02,0,pc);
  const q=textPlane('?',{w:1.2,h:1.0,color:'#ffd24a',size:600});q.position.set(0,0.9,0.1);pc.add(q);
  const noDate=textPlane('Kein Termin',{w:1.25,h:0.42,color:'#fff',bg:'#e0262b',size:130,radius:20});noDate.position.set(-0.8,2.98,1.8);scene.add(noDate);
  const konLbl=textPlane('Konsolen',{w:1.3,h:0.42,color:'#12183a',bg:'#ffd24a',size:120,radius:20});konLbl.position.set(0.8,2.98,1.8);scene.add(konLbl);
  const bubbles=[0,1,2].map(i=>{const b=textPlane('…',{w:1.3,h:0.8,color:'#222',bg:'#dcdce6',size:300,radius:60});b.position.set(-1+i*1.0,6.0,1.2);scene.add(b);return b});
  const stampG=textPlane('GERÜCHT',{w:3.0,h:0.9,color:'#fff',bg:'#7a1d8f',size:190,radius:40});stampG.position.set(0,5.2,1.6);stampG.rotation.z=0.12;scene.add(stampG);
  const tHeute=T(/^heute$/,0,0.2), tBest=T(/bestätigt|bestatigt/,0,D*0.1), tTake=T(/take/,0,D*0.2), tKons=T(/konsolen/,0,D*0.4), tPC=T(/^pc$/,0,D*0.5),
        tGer=T(/gerüchte|geruchte/,0,D*0.66), tFrage=T(/wirst/,0,D*0.8);
  const show=(o,v)=>{o.visible=v>0.001;o.scale.setScalar(Math.max(v,0.0001))};
  return {update(t){
    pageG.rotation.x=-ease(clamp((t-0.5)/0.7))*Math.PI*0.96; d18.visible=p18.visible=pageG.rotation.x>-1.4;
    cal.position.y=4.5+Math.sin(t*1.6)*0.05; cal.rotation.y=Math.sin(t*0.6)*0.12; cal.scale.setScalar(0.95*(1+(t>=tBest&&t<tBest+0.4?0.08*Math.sin((t-tBest)*Math.PI/0.4):0)));
    fig.armR.rotation.z=(t>=tBest)?-2.0+Math.sin(t*5)*0.15:0.25; fig.armL.rotation.z=0.25; fig.head.rotation.y=0.2+Math.sin(t*1.5)*0.2; fig.group.position.y=Math.abs(Math.sin(t*2.4))*0.04;
    const kp=pop((t-tKons)/0.5); show(con,t>=tKons?kp*0.55:0); show(konLbl,t>=tKons+0.2?pop((t-tKons-0.2)/0.4):0); con.rotation.y=t*1.2;
    const pp=pop((t-tPC)/0.5); show(pc,t>=tPC?pp*0.6:0); show(noDate,t>=tPC+0.5?pop((t-tPC-0.5)/0.4):0); q.rotation.z=Math.sin(t*5)*0.1;
    bubbles.forEach((b,i)=>{const s=t-tGer;const vis=s>-0.1&&s<2.2;b.visible=vis;b.position.y=6.0-Math.max(0,s-0.9)*3.2;b.position.x=-1+i*1.0+Math.sin(t*3+i)*0.05;b.scale.setScalar(vis?pop((s+0.1)/0.3):0.0001)});
    show(stampG,t>=tGer+0.4&&t<tGer+2.2?pop((t-tGer-0.4)/0.3):0);
    cam.position.set(lerp(-0.5,0.5,ease(clamp(t/D))), lerp(3.8,3.5,ease(clamp(t/D))), lerp(9.2,7.8,ease(clamp(t/D))));
    cam.lookAt(0,3.6,0);
  }}
}
