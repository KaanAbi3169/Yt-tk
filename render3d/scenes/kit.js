// Szenenbaukasten (Autopilot Stufe 2): Das Video wird nur beschrieben (scene.json), kein eigener Code je Video.
// Aufbau: set (Kulisse), figure (Kanalfigur), props (Bauteile), cams (Kameraeinstellungen), beats (Zeitpunkte nach Wörtern).
// Format und Beispiele: render3d/KIT.md
export default function(S){
  const {THREE,scene,cam,mat,add,textPlane,ease,clamp,lerp,pop,T,TE,D,makeFigure,photo,kit,norm,words}=S;
  if(!kit) throw new Error('scene.json fehlt');
  const C=c=>new THREE.Color(c);
  const arr=(v,n=3,d=0)=>Array.isArray(v)?v:Array(n).fill(v??d);
  // ---------- Kulissen ----------
  const SETS={
    sunset(){scene.background=C(0xff7a5a);scene.fog=new THREE.Fog(0xff7a5a,18,40);
      const sky=new THREE.Mesh(new THREE.PlaneGeometry(40,24),new THREE.MeshBasicMaterial({vertexColors:true}));const pos=sky.geometry.attributes.position,cs=[];
      for(let i=0;i<pos.count;i++){const k=(pos.getY(i)+12)/24;const c=C(0x3a1f7a).lerp(C(0xff8a4a),1-k);cs.push(c.r,c.g,c.b)}
      sky.geometry.setAttribute('color',new THREE.Float32BufferAttribute(cs,3));sky.position.set(0,9,-14);scene.add(sky);
      const sun=new THREE.Mesh(new THREE.CircleGeometry(3.2,40),new THREE.MeshBasicMaterial({color:0xffd24a}));sun.position.set(0,5.2,-13.5);scene.add(sun);
      add(new THREE.BoxGeometry(30,0.2,30),mat(0x241446),0,-0.1,-4);
      for(let i=-6;i<=6;i++)add(new THREE.BoxGeometry(0.05,0.02,30),new THREE.MeshBasicMaterial({color:0xff4fa0}),i*1.5,0.02,-4).castShadow=false},
    night(){scene.background=C(0x1d2a5b);scene.fog=new THREE.Fog(0x1d2a5b,16,34);
      add(new THREE.BoxGeometry(20,0.2,20),mat(0x2b3c7d),0,-0.1,0);add(new THREE.CylinderGeometry(2.6,2.8,0.25,40),mat(0x3d55b3),0,0.12,0)},
    room(){scene.background=C(0xbfe3f5);scene.fog=new THREE.Fog(0xbfe3f5,14,30);
      add(new THREE.BoxGeometry(14,0.2,14),mat(0xe9d3b0),0,-0.1,0);add(new THREE.BoxGeometry(14,9,0.2),mat(0x4f86c6),0,4.5,-4.2);
      add(new THREE.BoxGeometry(0.2,9,14),mat(0xf3b46b),-5.2,4.5,0);add(new THREE.BoxGeometry(3.2,2.2,0.15),mat(0xffe9a8),-1.2,5.6,-4.05);add(new THREE.BoxGeometry(2.6,1.6,0.2),mat(0x9fd3f2),-1.2,5.6,-3.98)},
    studio(){scene.background=C(0xe9edf5);scene.fog=new THREE.Fog(0xe9edf5,16,34);
      add(new THREE.BoxGeometry(24,0.2,24),mat(0xcfd6e6),0,-0.1,0);add(new THREE.BoxGeometry(24,10,0.2),mat(0xdfe6f4),0,5,-5);
      [[-3.5,0xff6b6b],[0,0xffd24a],[3.5,0x4fa3ff]].forEach(([x,c])=>add(new THREE.BoxGeometry(2.4,10,0.1),mat(c),x,5,-4.9))},
  };
  (SETS[kit.set||'night']||(()=>{throw new Error('Kulisse unbekannt: '+kit.set)}))();
  if(kit.bg)scene.background=C(kit.bg);
  // ---------- Bauteile ----------
  const P={};
  const MAKE={
    text:p=>textPlane(p.text||'',{w:p.w||2.6,h:p.h||0.9,color:p.color||'#fff',bg:p.bg||null,size:p.size||160,stroke:p.stroke||null,radius:p.radius||40}),
    stamp:p=>textPlane(p.text||'',{w:p.w||3,h:p.h||0.9,color:p.color||'#fff',bg:p.bg||'#e0262b',size:p.size||190,radius:p.radius||40}),
    bubble:p=>textPlane(p.text||'…',{w:p.w||1.3,h:p.h||0.8,color:p.color||'#222',bg:p.bg||'#dcdce6',size:p.size||300,radius:60}),
    counter:p=>textPlane((p.fmt||'{n}').replace('{n}',p.from??0),{w:p.w||2.6,h:p.h||1.1,color:p.color||'#ffd24a',size:p.size||330,stroke:p.stroke||'#12183a'}),
    box:p=>{const m=new THREE.Mesh(new THREE.BoxGeometry(...arr(p.size||1)),mat(C(p.color||'#ffffff')));m.castShadow=true;return m},
    sphere:p=>{const m=new THREE.Mesh(new THREE.SphereGeometry(p.r||0.5,20,14),mat(C(p.color||'#ffffff')));m.castShadow=true;return m},
    cylinder:p=>{const m=new THREE.Mesh(new THREE.CylinderGeometry(p.r||0.4,p.r||0.4,p.h||1,24),mat(C(p.color||'#ffffff')));m.castShadow=true;return m},
    bar:p=>{const g=new THREE.Group(),m=new THREE.Mesh(new THREE.BoxGeometry(p.w||0.5,1,p.d||0.4),mat(C(p.color||'#ffb020')));m.position.y=0.5;m.castShadow=true;g.add(m);g.userData.bar=true;return g},
    arrow:p=>{const g=new THREE.Group();const c=mat(C(p.color||'#ffd24a'));add(new THREE.CylinderGeometry(0.12,0.12,0.8,12),c,0,0.4,0,g);add(new THREE.ConeGeometry(0.3,0.5,16),c,0,-0.1,0,g);return g},
    monitor:p=>{const g=new THREE.Group();add(new THREE.BoxGeometry(1.9,1.2,0.12),mat(0x222233),0,0.9,0,g);add(new THREE.BoxGeometry(0.15,0.6,0.15),mat(0x222233),0,0.25,0,g);add(new THREE.BoxGeometry(0.9,0.06,0.5),mat(0x222233),0,-0.02,0,g);
      if(p.screen){const t=textPlane(p.screen,{w:1.2,h:1.0,color:p.screenColor||'#ffd24a',size:600});t.position.set(0,0.9,0.1);g.add(t);g.userData.screen=t}return g},
    console:p=>{const g=new THREE.Group();add(new THREE.BoxGeometry(0.5,1.6,1.3),mat(0xf3f3f7),0,0,0,g);add(new THREE.BoxGeometry(0.52,1.5,0.18),mat(0x15151f),0,0,0.2,g);return g},
    calendar:p=>{const g=new THREE.Group();add(new THREE.BoxGeometry(2.8,3.3,0.35),mat(0xffffff),0,0,0,g);add(new THREE.BoxGeometry(2.8,0.8,0.4),mat(0xe0262b),0,1.25,0.02,g);
      const mo=textPlane(p.month||'',{w:2.4,h:0.6,color:'#fff',size:150});mo.position.set(0,1.25,0.25);g.add(mo);
      const nu=textPlane(p.text||'',{w:2.4,h:1.9,color:'#1b1b33',size:700});nu.position.set(0,-0.35,0.2);g.add(nu);g.userData.num=nu;
      if(p.prev){const pg=new THREE.Group();pg.position.set(0,1.65,0.25);g.add(pg);add(new THREE.BoxGeometry(2.7,2.9,0.05),mat(0xfafafa),0,-1.45,0,pg);
        const pn=textPlane(p.prev,{w:2.4,h:1.9,color:'#1b1b33',size:700});pn.position.set(0,-1.55,0.05);pg.add(pn);g.userData.page=pg}
      for(const x of[-0.8,0,0.8])add(new THREE.CylinderGeometry(0.07,0.07,0.5,8),mat(0x333344),x,1.65,0.2,g).rotation.z=Math.PI/2;return g},
    photo:p=>photo(p.image,p.w||2.4),
    figure:p=>{const f=makeFigure({headScale:p.headScale||1,shirt:p.shirt?C(p.shirt):0xf07a1a,pants:p.pants?C(p.pants):0x2f5bd1});f.group.userData.fig=f;return f.group},
  };
  for(const p of kit.props||[]){
    if(!MAKE[p.type])throw new Error('Bauteil unbekannt: '+p.type);
    const o=MAKE[p.type](p);if(p.type!=='figure'&&o.parent!==scene)scene.add(o);
    const bs=arr(p.scale??1),bp=arr(p.pos,3,0);
    o.position.set(...bp);if(p.rot!==undefined){if(p.type==='figure')o.rotation.y=p.rot;else o.rotation.z=p.rot}
    P[p.id]={p,o,bs,bp,ev:[],vis:p.show===true||p.type==='figure'&&p.show!==false,baseRotY:o.rotation.y,baseRotZ:o.rotation.z};
    if(p.type==='bar'){P[p.id].h=p.h??1}
    o.scale.setScalar(1);
  }
  // ---------- Beats auflösen ----------
  const anchor=b=>{
    if(typeof b.at==='number')return b.at+(b.offset||0);
    const re=new RegExp(b.at,'i'),m=words.filter(w=>re.test(norm(w.w)))[b.n||0];
    if(m)return (b.end?m.e:m.s)+(b.offset||0);
    return b.fallback!==undefined?b.fallback*D:null};
  const camEv=[];
  for(const b of kit.beats||[]){
    const t=anchor(b);if(t===null){console.error('Anker nicht gefunden: '+b.at);continue}
    const e={...b,t};
    if(b.do==='cam'||b.do==='shake'){camEv.push(e);continue}
    if(!P[b.id])throw new Error('Beat mit unbekanntem Bauteil: '+b.id);
    P[b.id].ev.push(e)}
  camEv.sort((a,b)=>a.t-b.t);Object.values(P).forEach(r=>r.ev.sort((a,b)=>a.t-b.t));
  const POSE={idle:{r:0.25,l:0.25,hy:0,hx:0},point:{r:-2.0,l:0.25,hy:-0.4,hx:0},wave:{r:-2.6,l:0.25,hy:0.1,hx:0},think:{r:-1.1,l:0.25,hy:0.2,hx:0.15},cheer:{r:-2.7,l:2.7,hy:0,hx:-0.1},shrug:{r:0.9,l:-0.9,hy:0,hx:0.1}};
  const tween=(ev,t,init,get)=>{let cur=init;for(const e of ev){if(t<e.t)break;const pr=ease(clamp((t-e.t)/(e.dur||0.6)));const to=get(e);cur=cur.map?cur.map((c,i)=>lerp(c,to[i],pr)):lerp(cur,to,pr);if(pr<1)return cur;}return cur};
  const cam0=kit.cams?.start||{pos:[0,3.5,8],look:[0,3.5,0]};
  const count=new Map();
  return {update(t){
    for(const r of Object.values(P)){
      const {o,p}=r;let vis=r.vis,sc=1;
      for(const e of r.ev){if(t<e.t)break;if(e.do==='in'||e.do==='pop'){vis=true;sc=pop((t-e.t)/0.35)}else if(e.do==='out'){const k=clamp((t-e.t)/0.18);sc=1-k;vis=k<1}}
      let pos=tween(r.ev.filter(e=>e.do==='move'),t,r.bp,e=>e.to);
      let sy=null,mult=1,rotY=r.baseRotY;
      if(r.h!==undefined)sy=tween(r.ev.filter(e=>e.do==='grow'),t,r.h,e=>e.to);else mult=tween(r.ev.filter(e=>e.do==='grow'),t,1,e=>e.to);
      for(const e of r.ev){if(t<e.t)break;
        if(e.do==='spin')rotY+= (e.speed||1.2)*(t-e.t);
        if(e.do==='pulse'&&t<e.t+(e.dur||0.5))mult*=1+(e.amp||0.1)*Math.sin((t-e.t)/(e.dur||0.5)*Math.PI);
        if(e.do==='flip'&&o.userData.page){o.userData.page.rotation.x=-ease(clamp((t-e.t)/(e.dur||0.7)))*Math.PI*0.96;o.userData.page.visible=o.userData.page.rotation.x>-1.4}
        if(e.do==='count'){const pr=ease(clamp((t-e.t)/(e.dur||1.5)));const n=Math.round(lerp(e.from??0,e.to,pr));const txt=(e.fmt||p.fmt||'{n}').replace('{n}',n);if(count.get(p.id)!==txt){count.set(p.id,txt);o.userData.redraw(txt)}}}
      if(p.type==='calendar'&&o.userData.page&&!r.ev.some(e=>e.do==='flip'&&t>=e.t))o.userData.page.rotation.x=0;
      if(p.type==='figure'){const f=o.userData.fig;const pe=r.ev.filter(e=>e.do==='pose');let cur=POSE.idle,prev=POSE.idle,k=1;
        for(const e of pe){if(t<e.t)break;prev=cur;cur=POSE[e.pose]||POSE.idle;k=clamp((t-e.t)/0.3)}
        const ps=(a,b)=>lerp(a,b,k);const wob=(cur===POSE.wave?Math.sin(t*8)*0.3:cur===POSE.point?Math.sin(t*5)*0.12:0);
        f.armR.rotation.z=ps(prev.r,cur.r)+wob;f.armL.rotation.z=ps(prev.l,cur.l)+(cur===POSE.cheer?-wob:0);f.head.rotation.y=ps(prev.hy,cur.hy)+Math.sin(t*1.4)*0.15;f.head.rotation.x=ps(prev.hx,cur.hx);
        pos[1]=r.bp[1]+Math.abs(Math.sin(t*2.2))*0.03+(cur===POSE.cheer?Math.abs(Math.sin(t*5))*0.15:0)}
      o.visible=vis&&sc>0.001;o.position.set(pos[0],pos[1],pos[2]);o.rotation[p.type==='figure'?'y':'y']=rotY;
      if(sy!==null)o.scale.set(sc*r.bs[0],Math.max(0.01,sy)*sc*r.bs[1],sc*r.bs[2]);else o.scale.set(sc*mult*r.bs[0],sc*mult*r.bs[1],sc*mult*r.bs[2]);
      if(p.type!=='figure'&&p.rot!==undefined)o.rotation.z=r.baseRotZ;
    }
    // Kamera: Einstellungen nacheinander, dazu leichtes Schweben und Wackeln
    let pos=cam0.pos,look=cam0.look;
    for(const e of camEv){if(e.do!=='cam'||t<e.t)continue;const sh=kit.cams?.[e.shot];if(!sh)continue;const pr=ease(clamp((t-e.t)/(e.dur||1.2)));
      const np=pos.map((c,i)=>lerp(c,sh.pos[i],pr)),nl=look.map((c,i)=>lerp(c,sh.look[i],pr));if(pr<1){pos=np;look=nl;break}pos=sh.pos;look=sh.look}
    let sx=0,sy2=0;for(const e of camEv){if(e.do==='shake'&&t>=e.t&&t<e.t+(e.dur||0.5)){const k=1-(t-e.t)/(e.dur||0.5);sx+=Math.sin(t*60)*(e.amp||0.08)*k;sy2+=Math.cos(t*47)*(e.amp||0.08)*k}}
    const dr=kit.drift??0.35;cam.position.set(pos[0]+Math.sin(t*0.35)*dr+sx,pos[1]+sy2,pos[2]);cam.lookAt(...look);
  }}
}
