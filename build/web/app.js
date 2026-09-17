(function () {
'use strict';
const C = AtlasCore, $ = id => document.getElementById(id);
const el = (tag, text, cls) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if(cls) node.className = cls; return node; };
const button = (text, action, cls) => { const b = el('button', text, cls); b.type='button'; b.addEventListener('click', action); return b; };
const setText = (id, value) => { $(id).textContent = value; };
const storageKey = 'birthday-atlas:v2:' + DATA.version;
let edits = C.clone(DATA.edits), collection, currentView = 'journey', stopIndex = 0, selectedPlace, featuredFile, editing = false;
let panelIndex = 0, mapView = {scale:1,x:0,y:0}, lbFiles = [], lbIndex=0, lbOrigin=null, editOrigin=null, editAction=null;
let noticeTimer;
function notice(message) { setText('notice',message); $('notice').hidden=false; clearTimeout(noticeTimer); noticeTimer=setTimeout(() => {$('notice').hidden=true;},6000); }
try {
  const stored = localStorage.getItem(storageKey);
  if (stored) edits = C.merge(edits, C.validateEdits(DATA, JSON.parse(stored)));
} catch (e) { notice('Saved changes could not be loaded. The original collection is still here.'); }
const saver = C.createSaver(async value => { localStorage.setItem(storageKey, JSON.stringify(value)); }, state => {
  setText('saveStatus',state === 'saving' ? 'Saving…' : state === 'saved' ? 'Saved on this device' : 'Not saved. Retry or export your writing.');
  $('retrySave').hidden=state !== 'error';
  if(state==='error')notice('Changes are not saved yet. Retry saving or export your writing.');
});
function persist() { saver.queue(edits); refresh(); }
function refresh() {
  collection=C.resolve(DATA,edits);
  if (!collection.placeMap.has(selectedPlace) || (!editing && !collection.placeMap.get(selectedPlace).files.length)) selectedPlace=collection.places.find(p=>p.files.length)?.id;
  renderHeader(); renderJourney(); renderFilters(); renderTimeline(); renderPlaceIndex(); renderDetail();
  if(currentView==='map') renderMap();
  document.querySelectorAll('.editor-only').forEach(n=>{n.hidden=!editing;});
}
function photosAt(id) { return collection.placeMap.get(id)?.files || []; }
function caption(p) { return p.caption || (p.place ? 'A memory from ' + p.place.name : 'A family memory'); }
function photoMeta(p) { return [p.place?.name || 'Place not yet recorded', p.year || 'Year not yet recorded'].join(' · '); }
function span(years) { return years.length ? years[0] === years[years.length-1] ? String(years[0]) : years[0]+'–'+years[years.length-1] : ''; }
function setImageSource(img,src) { if(img.getAttribute('src')===src)return; img.style.opacity='0';img.onload=()=>{img.style.opacity='1';};img.onerror=()=>{img.style.opacity='1';notice('A photograph or map could not load. Please try again.');};img.src=src;if(img.complete)img.style.opacity='1'; }
function image(id,p,thumbnail=false) { if(!p) return; const img=$(id); setImageSource(img,thumbnail?p.thumb:p.full); img.alt=caption(p); img.width=p.w;img.height=p.h; }
function renderHeader() {
  setText('title',collection.meta.title); document.title=collection.meta.title;
  setText('dedication',collection.meta.dedication);
  const years=[...new Set(collection.photos.map(p=>p.year).filter(Boolean))].sort((a,b)=>a-b);
  const places=collection.places.filter(p=>p.files.length).length;
  setText('edition',span(years)+' · A birthday collection');
  setText('collectionStats',collection.photos.length+' photographs · '+places+' places · '+span(years));
  setText('footerStats',collection.photos.length+' photographs, collected with love.');
  const hero=collection.photoMap.get(DATA.journey.hero);
  image('heroImg',hero);setText('heroCaption',photoMeta(hero)+' · '+caption(hero));
}
function showView(view,{scroll=true,hideOpening=true}={}) {
  currentView=view;
  if(hideOpening)$('opening').hidden=true;
  ['journey','map','timeline'].forEach(v=>{$(v+'View').hidden=v!==view;});
  document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));
  if(view==='map')renderMap();
  if(scroll) {$('main').scrollIntoView({block:'start'});$('main').focus({preventScroll:true});}
}
function renderJourney() {
  const stop=DATA.journey.stops[stopIndex],p=collection.photoMap.get(stop.file);
  image('journeyImg',p); setText('journeyChapter',stop.chapter);setText('journeyYear',p.year||'');setText('journeyTitle',stop.title);
  setText('journeyLocation',p.place?.name||'A family memory');
  const separate=p.caption && p.caption.toLowerCase().replace(/[!.]/g,'')!==stop.title.toLowerCase().replace(/[!.]/g,'');
  setText('journeyCaption',separate?p.caption:'');$('journeyCaption').hidden=!separate;
  setText('journeyPosition',String(stopIndex+1).padStart(2,'0')+' / '+DATA.journey.stops.length);
  setText('journeyCount',DATA.journey.stops.length+' selected memories');
  $('journeyPrev').disabled=stopIndex===0;$('journeyNext').disabled=stopIndex===DATA.journey.stops.length-1;
  $('journeyEnding').hidden=stopIndex!==DATA.journey.stops.length-1;
  const host=$('journeyProgress');host.replaceChildren();
  DATA.journey.stops.forEach((s,i)=>{const b=button('',()=>{stopIndex=i;renderJourney();});b.setAttribute('aria-label','Memory '+(i+1)+': '+s.title);b.setAttribute('aria-current',String(i===stopIndex));host.append(b);});
}
function choosePlace(id,{focus=true,fit=true,file=null}={}) {
  if(!collection.placeMap.has(id))return;
  selectedPlace=id;featuredFile=file||null;
  const p=collection.placeMap.get(id);
  if(fit){panelIndex=bestPanel([p]);mapView={scale:1,x:0,y:0};}
  renderPlaceIndex();renderDetail();renderMap();
  if(fit && DATA.panels[panelIndex].id==='world') focusPoints([p],3.5);
  if(focus){const target=matchMedia('(max-width:720px)').matches?$('placeDetail'):$('mapView');target.scrollIntoView({block:'start'});if(target===$('placeDetail'))target.focus({preventScroll:true});}
}
function visiblePlaces() { return collection.places.filter(p=>p.files.length||editing); }
function renderPlaceIndex() {
  const host=$('placeIndex');host.replaceChildren();const places=visiblePlaces();
  setText('placeCount',places.length+' places');
  places.forEach((p,i)=>{
    const b=button('',()=>choosePlace(p.id));b.setAttribute('aria-current',String(p.id===selectedPlace));
    b.append(el('small',String(i+1).padStart(2,'0')),el('strong',p.name),el('small',p.files.length+(p.files.length===1?' photo · ':' photos · ')+span(p.years)));host.append(b);
  });
}
function renderDetail() {
  const p=collection.placeMap.get(selectedPlace);if(!p)return;
  setText('placeName',p.name);setText('placeMeta',[span(p.years),p.files.length+(p.files.length===1?' photograph':' photographs')].filter(Boolean).join(' · '));
  setText('placeStory',p.story||'');$('placeStory').hidden=!p.story;
  if(!p.files.includes(featuredFile))featuredFile=p.cover;
  const featured=collection.photoMap.get(featuredFile);
  $('featuredOpen').hidden=!featured;
  if(featured){image('featuredImg',featured);setText('featuredCaption',caption(featured)+(featured.year?' · '+featured.year:''));}else setText('featuredCaption','Add a photograph to this place in the editor.');
  const gallery=$('gallery');gallery.replaceChildren();
  for(const file of p.files){const photo=collection.photoMap.get(file),b=button('',()=>{featuredFile=file;renderDetail();});b.setAttribute('aria-label','Feature '+caption(photo)+', '+(photo.year||'year unknown'));b.setAttribute('aria-current',String(file===featuredFile));const im=el('img');im.src=photo.thumb;im.alt=caption(photo);im.loading='lazy';im.width=photo.w;im.height=photo.h;b.append(im);gallery.append(b);}
}
const merc = lat => {const s=Math.sin(Math.max(-85,Math.min(85,lat))*Math.PI/180);return .5-Math.log((1+s)/(1-s))/(4*Math.PI);};
function inside(p,s) {return p.lng>=s.west&&p.lng<=s.east&&p.lat>=s.south&&p.lat<=s.north;}
function project(p,s) {return {x:(p.lng-s.west)/(s.east-s.west),y:(merc(p.lat)-merc(s.north))/(merc(s.south)-merc(s.north))};}
function bestPanel(points) {let best=0,area=Infinity;DATA.panels.forEach((s,i)=>{const a=(s.east-s.west)*(merc(s.south)-merc(s.north));if(points.every(p=>inside(p,s))&&a<area){area=a;best=i;}});return best;}
function dimensions() {const s=DATA.panels[panelIndex],chart=$('chart'),width=chart.clientWidth,height=chart.clientHeight;const base=Math.min(width,height*s.w/s.h);return {width,height,base,baseH:base*s.h/s.w};}
function applyMapView() {
  const d=dimensions(),w=d.base*mapView.scale,h=d.baseH*mapView.scale;
  mapView.x=w<=d.width?(d.width-w)/2:Math.min(0,Math.max(d.width-w,mapView.x));
  mapView.y=h<=d.height?(d.height-h)/2:Math.min(0,Math.max(d.height-h,mapView.y));
  const stage=$('mapStage');stage.style.width=w+'px';stage.style.height=h+'px';stage.style.left=mapView.x+'px';stage.style.top=mapView.y+'px';
  $('chart').classList.toggle('zoomed',mapView.scale>1);$('zoomOut').disabled=mapView.scale<=1;$('zoomIn').disabled=mapView.scale>=8;
}
function renderMap() {
  if(currentView!=='map')return;
  const s=DATA.panels[panelIndex];setImageSource($('mapImg'),s.src);$('mapImg').alt='Map of '+s.title;
  const select=$('sheetSelect');select.replaceChildren();DATA.panels.forEach((panel,i)=>{const o=el('option',panel.title);o.value=String(i);select.append(o);});select.value=String(panelIndex);
  applyMapView();renderPins();
}
function renderPins() {
  if(currentView!=='map')return;
  const s=DATA.panels[panelIndex],d=dimensions(),w=d.base*mapView.scale,h=d.baseH*mapView.scale;
  const points=visiblePlaces().filter(p=>inside(p,s)).map(p=>({...project(p,s),place:p}));
  const groups=[];
  for(const p of points){let group=groups.find(g=>g.some(q=>Math.hypot((p.x-q.x)*w,(p.y-q.y)*h)<48));if(group)group.push(p);else groups.push([p]);}
  // Merge transitive collisions so no two resulting tap targets overlap.
  for(let a=0;a<groups.length;a++)for(let b=a+1;b<groups.length;b++)if(groups[a].some(p=>groups[b].some(q=>Math.hypot((p.x-q.x)*w,(p.y-q.y)*h)<48))){groups[a].push(...groups.splice(b,1)[0]);b=a;}
  const host=$('pins');host.replaceChildren();
  for(const group of groups){const x=group.reduce((n,p)=>n+p.x,0)/group.length,y=group.reduce((n,p)=>n+p.y,0)/group.length;
    const b=button(group.length>1?String(group.length):'',()=>group.length>1?openCluster(group.map(p=>p.place)):choosePlace(group[0].place.id),group.length>1?'pin cluster':'pin');
    b.style.left=x*100+'%';b.style.top=y*100+'%';b.setAttribute('aria-label',group.length>1?'Explore '+group.length+' places: '+group.map(p=>p.place.name).join(', '):group[0].place.name+', '+group[0].place.files.length+' photographs');
    if(group.length===1){b.setAttribute('aria-current',String(group[0].place.id===selectedPlace));b.append(el('span',group[0].place.name));}host.append(b);
  }
}
function focusPoints(points,minScale=1) {
  const s=DATA.panels[panelIndex],d=dimensions(),coords=points.map(p=>project(p,s));
  const xs=coords.map(p=>p.x),ys=coords.map(p=>p.y),cx=(Math.min(...xs)+Math.max(...xs))/2,cy=(Math.min(...ys)+Math.max(...ys))/2;
  const scale=Math.max(minScale,Math.min(6,d.width*.66/(Math.max(.04,Math.max(...xs)-Math.min(...xs))*d.base),d.height*.66/(Math.max(.04,Math.max(...ys)-Math.min(...ys))*d.baseH)));
  mapView={scale,x:d.width/2-cx*d.base*scale,y:d.height/2-cy*d.baseH*scale};applyMapView();renderPins();
}
function openCluster(places) {
  const next=bestPanel(places),changed=next!==panelIndex;panelIndex=next;mapView={scale:1,x:0,y:0};
  if(!places.some(p=>p.id===selectedPlace)){selectedPlace=places[0].id;featuredFile=null;renderDetail();renderPlaceIndex();}
  renderMap();if(!changed||DATA.panels[next].id==='world')focusPoints(places,1.8);
  const choices=$('clusterChoices');choices.replaceChildren(el('p','Choose a place in this group'));
  places.forEach(p=>choices.append(button(p.name,()=>choosePlace(p.id))));choices.hidden=false;
  choices.querySelector('button')?.focus({preventScroll:true});
}
function zoom(factor,cx,cy) {
  const d=dimensions();cx=cx??d.width/2;cy=cy??d.height/2;
  const scale=Math.max(1,Math.min(8,mapView.scale*factor)),ratio=scale/mapView.scale;
  mapView.x=cx-(cx-mapView.x)*ratio;mapView.y=cy-(cy-mapView.y)*ratio;mapView.scale=scale;applyMapView();renderPins();
}
function chapter(p) {
  const stop=DATA.journey.stops.find(s=>s.file===p.file);if(stop)return stop.chapter;
  if(p.year&&p.year<2015)return 'The early years';
  const cap=p.caption||'';
  if(/wedding|dancefloor/i.test(cap))return 'The wedding';
  if(/birthday|graduation|engagement|renewal|gala/i.test(cap))return 'Family celebrations';
  if(/dinner|breakfast|bbq/i.test(cap))return 'Around the table';
  if(/hiking|biking|paris|australia|lodge|wells|washington|rocks|loop/i.test(cap))return 'Out in the world';
  return 'Everyday moments';
}
function options(id,items,first) {const select=$(id),value=select.value;select.replaceChildren();const o=el('option',first);o.value='';select.append(o);items.forEach(([val,name])=>{const option=el('option',name);option.value=val;select.append(option);});select.value=items.some(i=>String(i[0])===value)?value:'';}
function renderFilters() {
  options('yearFilter',[...new Set(collection.photos.map(p=>p.year).filter(Boolean))].sort((a,b)=>a-b).map(y=>[String(y),String(y)]),'Every year');
  options('chapterFilter',[...new Set(collection.photos.map(chapter))].sort().map(v=>[v,v]),'Every chapter');
  options('placeFilter',collection.places.filter(p=>p.files.length).map(p=>[p.id,p.name]),'Every place');
}
function renderTimeline() {
  const photos=collection.photos.filter(p=>(!$('yearFilter').value||String(p.year)===$('yearFilter').value)&&(!$('chapterFilter').value||chapter(p)===$('chapterFilter').value)&&(!$('placeFilter').value||p.waypoint===$('placeFilter').value));
  const host=$('timeline');host.replaceChildren();setText('timelineCount',photos.length+' of '+collection.photos.length+' photographs');
  const grouped=new Map();photos.forEach(p=>{const y=p.year||'Year unknown';if(!grouped.has(y))grouped.set(y,[]);grouped.get(y).push(p);});
  for(const [year,group] of grouped){const section=el('section',undefined,'year-group'),heading=el('h3',String(year)),grid=el('div',undefined,'timeline-grid');section.append(heading,grid);host.append(section);
    group.forEach(p=>{const b=button('',()=>openLightbox(photos.map(p=>p.file),p.file,b),'memory-card');const img=el('img');img.src=p.thumb;img.alt=caption(p);img.loading='lazy';img.width=p.w;img.height=p.h;b.append(img,el('strong',caption(p)),el('small',p.place?.name||'Place not recorded'));grid.append(b);});
  }
  if(!photos.length)host.append(el('p','No photographs match these filters. Try another year, chapter, or place.','empty'));
}
function openLightbox(files,file,origin=document.activeElement) {
  lbFiles=files;lbIndex=Math.max(0,files.indexOf(file));lbOrigin=origin;paintLightbox();
  $('lightbox').showModal();document.body.classList.add('modal-open');$('lbClose').focus();
}
function paintLightbox(){const p=collection.photoMap.get(lbFiles[lbIndex]);if(!p)return;image('lbImg',p);setText('lbCaption',caption(p));setText('lbMeta',photoMeta(p));setText('lbCount',(lbIndex+1)+' / '+lbFiles.length);$('lbPrev').disabled=lbIndex===0;$('lbNext').disabled=lbIndex===lbFiles.length-1;}
function closeLightbox(){$('lightbox').close();}
$('lightbox').addEventListener('close',()=>{document.body.classList.remove('modal-open');if(lbOrigin?.isConnected)lbOrigin.focus({preventScroll:true});else $('main').focus({preventScroll:true});});
$('lightbox').addEventListener('keydown',e=>{if(e.key==='ArrowLeft'&&lbIndex>0){e.preventDefault();lbIndex--;paintLightbox();}if(e.key==='ArrowRight'&&lbIndex<lbFiles.length-1){e.preventDefault();lbIndex++;paintLightbox();}});
function field(name,label,type,value,{options:choices,required=false,min,max,step}={}) {
  const l=el('label',label),input=el(type==='textarea'?'textarea':type==='select'?'select':'input');input.name=name;input.id='field_'+name;input.required=required;
  if(type!=='textarea'&&type!=='select')input.type=type;
  if(choices)choices.forEach(([val,text])=>{const o=el('option',text);o.value=val;input.append(o);});
  if(min!==undefined)input.min=min;if(max!==undefined)input.max=max;if(step!==undefined)input.step=step;input.value=value??'';l.append(input);$('editFields').append(l);return input;
}
function openEditor(title,build,save) {
  editOrigin=document.activeElement;setText('editHeading',title);$('editFields').replaceChildren();setText('editError','');editAction=save;build();$('editDialog').showModal();document.body.classList.add('modal-open');$('editFields').querySelector('input,textarea,select')?.focus();
}
function closeEditor(){$('editDialog').close();}
$('editDialog').addEventListener('close',()=>{if(!$('lightbox').open)document.body.classList.remove('modal-open');if(editOrigin?.isConnected)editOrigin.focus({preventScroll:true});});
$('editForm').addEventListener('submit',e=>{e.preventDefault();try {editAction(new FormData($('editForm')));persist();if($('lightbox').open)paintLightbox();closeEditor();}catch(err){setText('editError',err.message);}});
function editCurrentPhoto() {
  const p=collection.photoMap.get(lbFiles[lbIndex]);
  openEditor('Edit this photograph',()=>{field('caption','Caption','textarea',p.caption);field('year','Year taken','number',p.year,{min:1900,max:2100,step:1});field('waypoint','Place','select',p.waypoint,{options:[['','Place not yet recorded'],...collection.places.map(w=>[w.id,w.name])]});$('editFields').append(el('p','You can correct the place of any photograph. Add a new place from the editing tools if needed.','field-help'));},values=>{
    const value=values.get('year'),year=value?Number(value):null;if(year!==null&&(!Number.isInteger(year)||year<1900||year>2100))throw Error('Enter a year between 1900 and 2100.');
    if(values.get('waypoint')!==p.waypoint && edits.waypoints[p.waypoint]?.cover===p.file) delete edits.waypoints[p.waypoint].cover;
    edits.photos[p.file]={...edits.photos[p.file],caption:values.get('caption').trim(),year,waypoint:values.get('waypoint'),placed:!!values.get('waypoint')};
  });
}
function editCurrentPlace() {
  const p=collection.placeMap.get(selectedPlace);
  openEditor('Edit '+p.name,()=>{field('name','Place name','text',p.name,{required:true});field('story','A note about this place','textarea',p.story);field('cover','Featured photograph','select',p.cover||'',{options:p.files.map(f=>{const photo=collection.photoMap.get(f);return [f,caption(photo)+' · '+(photo.year||'year unknown')];})});},values=>{if(!values.get('name').trim())throw Error('Enter a place name.');edits.waypoints[p.id]={...edits.waypoints[p.id],name:values.get('name').trim(),story:values.get('story').trim(),cover:values.get('cover')||''};featuredFile=values.get('cover')||null;});
}
let gazPromise;
function loadGazetteer(){if(gazPromise)return gazPromise;gazPromise=new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='gazetteer.js';script.onload=()=>{if(!window.__GAZ){reject(Error('Search is unavailable. You can enter coordinates below.'));return;}resolve(window.__GAZ.split('\n'));};script.onerror=()=>reject(Error('Search is unavailable. You can enter coordinates below.'));document.head.append(script);});return gazPromise;}
function addNewPlace(){
  openEditor('Add a place',()=>{
    const name=field('name','Search for a town or city','text','',{required:true}),results=el('div',undefined,'place-results');$('editFields').append(results);
    const lat=field('lat','Latitude','number','',{required:true,min:-85,max:85,step:'any'}),lng=field('lng','Longitude','number','',{required:true,min:-180,max:180,step:'any'});
    $('editFields').append(el('p','Choose a search result, or enter a name and coordinates for an exact spot.','field-help'));
    let request=0;
    name.addEventListener('input',async()=>{const id=++request,q=name.value.trim().toLowerCase();results.replaceChildren();if(q.length<2)return;try{const lines=await loadGazetteer();if(id!==request)return;const matches=lines.filter(line=>line.slice(0,line.indexOf('|')).toLowerCase().startsWith(q)).slice(0,8);for(const line of matches){const [n,admin,country,a,b]=line.split('|');results.append(button([n,admin,country].filter(Boolean).join(', '),()=>{name.value=n;lat.value=a;lng.value=b;results.replaceChildren();}));}}catch(err){setText('editError',err.message);}});
  },values=>{const name=values.get('name').trim(),lat=Number(values.get('lat')),lng=Number(values.get('lng'));if(!name||!Number.isFinite(lat)||Math.abs(lat)>85||!Number.isFinite(lng)||Math.abs(lng)>180)throw Error('Enter a name and valid coordinates.');let base='cu_'+name.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'_').slice(0,30),id=base,n=2;while(collection.placeMap.has(id))id=base+'_'+n++;edits.places[id]={name,lat,lng};});
}
function setEditing(value){editing=value;$('editorBar').hidden=!editing;refresh();if(value){$('editorBar').scrollIntoView({block:'center'});notice('Editing your copy. Select a photograph to change its caption, year, or place.');}else notice(saver.isDirty()?'Back to the gift. Your changes are not saved yet; export your writing or retry.':'Back to the gift. Your changes are saved on this device.');}
$('toggleEditor').onclick=()=>setEditing(true);$('finishEditing').onclick=()=>setEditing(false);$('retrySave').onclick=()=>saver.flush();
$('editIntro').onclick=()=>openEditor('Title & dedication',()=>{field('title','Title','text',collection.meta.title,{required:true});field('dedication','Dedication','textarea',collection.meta.dedication);},values=>{if(!values.get('title').trim())throw Error('Enter a title.');edits.meta.title=values.get('title').trim();edits.meta.dedication=values.get('dedication').trim();});
$('editPhoto').onclick=editCurrentPhoto;$('editPlace').onclick=editCurrentPlace;$('addPlace').onclick=addNewPlace;
$('editClose').onclick=closeEditor;$('editCancel').onclick=closeEditor;
$('exportWriting').onclick=()=>{const blob=new Blob([JSON.stringify(edits,null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download='birthday-atlas-writing.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notice('Writing exported. Use it with the build command to update the shared atlas.');};
$('importWriting').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;const imported=C.validateEdits(DATA,JSON.parse(await file.text()));edits=C.merge(edits,imported);persist();notice('Writing imported into your copy.');}catch(err){notice('Could not import: '+err.message);}finally{e.target.value='';}};
$('home').onclick=()=>{$('opening').hidden=false;showView('journey',{scroll:false,hideOpening:false});window.scrollTo({top:0,behavior:'smooth'});};
$('startJourney').onclick=()=>{stopIndex=0;renderJourney();showView('journey');};$('exploreMap').onclick=()=>showView('map');
$('allMemories').onclick=()=>showView('timeline');document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>showView(b.dataset.view));
$('journeyPrev').onclick=()=>{if(stopIndex>0)stopIndex--;renderJourney();};$('journeyNext').onclick=()=>{if(stopIndex<DATA.journey.stops.length-1)stopIndex++;renderJourney();};
$('journeyMap').onclick=()=>{const p=collection.photoMap.get(DATA.journey.stops[stopIndex].file);if(!p.place){notice('This photograph does not have a place yet.');return;}showView('map');choosePlace(p.waypoint,{file:p.file});};
$('heroOpen').onclick=()=>openLightbox(collection.photos.map(p=>p.file),DATA.journey.hero,$('heroOpen'));
$('journeyOpen').onclick=()=>openLightbox(DATA.journey.stops.map(s=>s.file),DATA.journey.stops[stopIndex].file,$('journeyOpen'));
$('featuredOpen').onclick=()=>openLightbox(photosAt(selectedPlace),featuredFile,$('featuredOpen'));
$('lbClose').onclick=closeLightbox;$('lbPrev').onclick=()=>{if(lbIndex>0)lbIndex--;paintLightbox();};$('lbNext').onclick=()=>{if(lbIndex<lbFiles.length-1)lbIndex++;paintLightbox();};
$('placePrev').onclick=()=>stepPlace(-1);$('placeNext').onclick=()=>stepPlace(1);
function stepPlace(delta){const places=visiblePlaces(),i=places.findIndex(p=>p.id===selectedPlace);choosePlace(places[(i+delta+places.length)%places.length].id);}
$('sheetSelect').onchange=()=>{panelIndex=Number($('sheetSelect').value);mapView={scale:1,x:0,y:0};$('clusterChoices').hidden=true;const places=visiblePlaces().filter(p=>inside(p,DATA.panels[panelIndex]));if(places.length){if(!places.some(p=>p.id===selectedPlace))selectedPlace=places[0].id;featuredFile=null;renderDetail();renderPlaceIndex();}renderMap();};
$('zoomIn').onclick=()=>zoom(1.5);$('zoomOut').onclick=()=>zoom(1/1.5);$('zoomReset').onclick=()=>{mapView={scale:1,x:0,y:0};renderMap();};
let drag=null;
$('chart').addEventListener('pointerdown',e=>{if(e.target.closest('button,a')||mapView.scale<=1)return;drag={id:e.pointerId,x:e.clientX,y:e.clientY};$('chart').setPointerCapture(e.pointerId);});
$('chart').addEventListener('pointermove',e=>{if(!drag||e.pointerId!==drag.id)return;mapView.x+=e.clientX-drag.x;mapView.y+=e.clientY-drag.y;drag.x=e.clientX;drag.y=e.clientY;applyMapView();});
['pointerup','pointercancel'].forEach(event=>$('chart').addEventListener(event,()=>{drag=null;}));
$('chart').addEventListener('wheel',e=>{if(!e.ctrlKey&&!e.metaKey)return;e.preventDefault();const r=$('chart').getBoundingClientRect();zoom(e.deltaY<0?1.15:1/1.15,e.clientX-r.left,e.clientY-r.top);},{passive:false});
['yearFilter','chapterFilter','placeFilter'].forEach(id=>$(id).onchange=renderTimeline);$('clearFilters').onclick=()=>{['yearFilter','chapterFilter','placeFilter'].forEach(id=>{$(id).value='';});renderTimeline();};
window.addEventListener('resize',()=>{if(currentView==='map'){mapView={scale:1,x:0,y:0};renderMap();}});
window.addEventListener('beforeunload',e=>{if(saver.isDirty()){e.preventDefault();e.returnValue='';}});
window.addEventListener('online',()=>saver.flush());
refresh();
})();
