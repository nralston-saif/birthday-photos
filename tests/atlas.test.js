const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const C=require('../build/web/core.js');
const html=fs.readFileSync(require('node:path').join(__dirname,'../site/publish/index.html'),'utf8');
const data=JSON.parse(html.match(/var DATA = (.*);<\/script>/)[1]);

test('birthday message paragraphs and sign-off survive validation, export, and resolution',()=>{
 const meta={card_message:'First paragraph.\n\nA second paragraph.\nAnother line.',card_signature:'With love'};
 const imported=C.validateEdits(data,JSON.parse(JSON.stringify({meta})));
 assert.deepEqual(imported.meta,meta);
 const resolved=C.resolve(data,C.merge(data.edits,imported));
 assert.equal(resolved.meta.card_message,meta.card_message);
 assert.equal(resolved.meta.card_signature,meta.card_signature);
 assert.equal(resolved.meta.dedication,'Happy Birthday Dad!');
 assert.throws(()=>C.validateEdits(data,{meta:{card_message:{body:'invalid'}}}),/Invalid text/);
});

test('birthday card is first-visit only after dismissal and survives a new visit',()=>{
 const saved=new Map(),storage={getItem:key=>saved.get(key),setItem:(key,value)=>saved.set(key,value)};
 const first=C.createCardVisit(storage);
 assert.equal(first.shouldShow(),true);
 assert.equal(C.createCardVisit(storage).shouldShow(),true);
 first.dismiss();
 assert.equal(first.shouldShow(),false);
 assert.equal(C.createCardVisit(storage).shouldShow(),false);
 assert.equal(saved.size,1);
});

test('blocked browser storage never traps someone in the birthday card',()=>{
 const storage={getItem(){throw Error('denied');},setItem(){throw Error('denied');}};
 const visit=C.createCardVisit(storage);
 assert.equal(visit.shouldShow(),true);
 assert.doesNotThrow(()=>visit.dismiss());
 assert.equal(visit.shouldShow(),false);
});

test('place search finds accented names and regions without changing the collection',()=>{
 const model=C.resolve(data,data.edits), places=model.places;
 assert.deepEqual(C.findPlaces(places,' da nang ').map(p=>p.name),['Đà Nẵng']);
 assert.deepEqual(C.findPlaces(places,'france paris').map(p=>p.name),['Paris']);
 assert.equal(C.findPlaces(places,'california').some(p=>p.name==='Atherton'),true);
 assert.equal(C.findPlaces(places,'no such place').length,0);
 assert.equal(C.findPlaces(places,'  ').length,16);
 assert.equal(places.length,16);
});

test('all 61 photographs are assigned exactly once, including the authored locations',()=>{
 const model=C.resolve(data,data.edits);
 assert.equal(model.photos.length,61);assert.equal(model.places.filter(p=>p.files.length).length,16);
 const files=model.places.flatMap(p=>p.files);assert.equal(files.length,61);assert.equal(new Set(files).size,61);
 assert.equal(model.photoMap.get('IMG_8386.HEIC').place.name,'Barcelona');
 assert.equal(model.places.find(p=>p.id==='wp_atherton').files.includes('IMG_8386.HEIC'),false);
 assert.equal(model.photos[0].year,2002);assert.equal(model.photos.at(-1).year,2026);
 assert.equal(model.meta.dedication,'Happy Birthday Dad!');
 assert.equal(model.photos.filter(p=>p.caption).length,41);
});

test('GPS-assigned photographs can move and dates re-sort the collection',()=>{
 const edits=C.clone(data.edits);edits.photos['IMG_0147.HEIC']={caption:'A changed caption',year:2001,waypoint:'cu_melbourne'};
 const m=C.resolve(data,edits),p=m.photoMap.get('IMG_0147.HEIC');
 assert.equal(p.place.name,'Melbourne');assert.equal(m.photos[0].file,p.file);
 assert.equal(m.placeMap.get('wp_paris').files.includes(p.file),false);
 assert.equal(m.placeMap.get('cu_melbourne').years[0],2001);
 edits.photos[p.file].waypoint='';edits.photos[p.file].year=null;const unplaced=C.resolve(data,edits).photoMap.get(p.file);
 assert.equal(unplaced.place,undefined);assert.equal(unplaced.year,null);
});

test('writing export round-trips, rejects unknown references, and preserves empty captions',()=>{
 assert.deepEqual(C.validateEdits(data,JSON.parse(JSON.stringify(data.edits))),data.edits);
 assert.throws(()=>C.validateEdits(data,{photos:{missing:{caption:'x'}}}),/Unknown photograph/);
 assert.throws(()=>C.validateEdits(data,{photos:{'IMG_0147.HEIC':{waypoint:'missing'}}}),/missing/);
 assert.throws(()=>C.validateEdits(data,{photos:{'IMG_0147.HEIC':{year:2020.5}}}),/Years/);
 const m=C.resolve(data,C.merge(data.edits,{photos:{'IMG_0147.HEIC':{caption:''}}}));
 assert.equal(m.photoMap.get('IMG_0147.HEIC').caption,'');
});

test('failed saves stay pending and retry the same document before reporting saved',async()=>{
 const attempts=[],statuses=[],timers=[];let fail=true;
 const saver=C.createSaver(async value=>{attempts.push(value);if(fail)throw Error('unavailable');},s=>statuses.push(s),fn=>timers.push(fn));
 await saver.queue({year:2002});assert.equal(saver.isDirty(),true);assert.equal(statuses.includes('saved'),false);assert.equal(timers.length,1);
 fail=false;timers.shift()();await new Promise(r=>setImmediate(r));
 assert.deepEqual(attempts,[{year:2002},{year:2002}]);assert.equal(saver.isDirty(),false);assert.equal(statuses.at(-1),'saved');
});

test('newer edits arriving during a save are serialized, not overwritten',async()=>{
 const attempts=[],release=[];
 const saver=C.createSaver(value=>{attempts.push(value);return new Promise(resolve=>release.push(resolve));},()=>{});
 const task=saver.queue({caption:'first'});saver.queue({caption:'second'});
 release.shift()();await new Promise(r=>setImmediate(r));
 assert.equal(saver.isDirty(),true);assert.deepEqual(attempts,[{caption:'first'},{caption:'second'}]);
 release.shift()();await task;assert.equal(saver.isDirty(),false);
});

test('repeated storage failure never claims saved and remains manually retryable',async()=>{
 const timers=[],status=[];let unavailable=true;
 const saver=C.createSaver(async()=>{if(unavailable)throw Error('quota');},s=>status.push(s),fn=>timers.push(fn));
 await saver.queue({title:'A gift'});
 while(timers.length){timers.shift()();await new Promise(r=>setImmediate(r));}
 assert.equal(status.includes('saved'),false);assert.equal(saver.isDirty(),true);
 unavailable=false;await saver.flush();assert.equal(saver.isDirty(),false);assert.equal(status.at(-1),'saved');
});
