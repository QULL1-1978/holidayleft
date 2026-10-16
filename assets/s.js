(function(){
function $(i){return document.getElementById(i)}
function set(i,t){var e=$(i);if(e)e.textContent=t}
function dn(s){var p=s.split('-');return Date.UTC(+p[0],+p[1]-1,+p[2])/864e5}
function iso(n){return new Date(n*864e5).toISOString().slice(0,10)}
function today(tz){
  try{return new Intl.DateTimeFormat('en-CA',{timeZone:tz||undefined,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}
  catch(e){var d=new Date();return d.getFullYear()+'-'+('0'+(d.getMonth()+1)).slice(-2)+'-'+('0'+d.getDate()).slice(-2)}
}
function fmt(s){return new Date(dn(s)*864e5).toLocaleDateString('en-GB',{timeZone:'UTC',weekday:'long',day:'numeric',month:'long',year:'numeric'})}
function plural(n,w){return n+' '+w+(n===1?'':'s')}
function nextOf(list,t){for(var i=0;i<list.length;i++){if(list[i][0]>=t)return list[i]}return null}
function inDays(n){return n===0?'today':n===1?'tomorrow':'in '+n+' days'}

/* theme toggle */
var tb=$('theme');
if(tb){tb.onclick=function(){
  var cur=document.documentElement.getAttribute('data-theme');
  if(!cur)cur=(window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';
  var nx=cur==='dark'?'light':'dark';
  document.documentElement.setAttribute('data-theme',nx);
  try{localStorage.setItem('theme',nx)}catch(e){}
}}

/* page data */
var el=$('d');
if(el){
  var D=JSON.parse(el.textContent);
  if(D.type==='until'||D.type==='country'){
    var t=today(D.type==='country'?D.tz:null),n=nextOf(D.dates,t);
    if(n){
      var diff=dn(n[0])-dn(t);
      set('days',String(diff));
      set('unit',diff===1?'day':'days');
      set('when',fmt(n[0]));
      if(D.type==='country')set('nname',n[1]);
      if($('wk'))set('wk',diff>=7?'That is '+plural(Math.floor(diff/7),'week')+(diff%7?' and '+plural(diff%7,'day'):'')+'.':(diff===0?'That is today!':''));
    }
  }
  if(D.type==='isday'){
    var t0=today(D.tz),tg=iso(dn(t0)+D.offset),h=D.h[tg],a=$('ans');
    if(a){a.textContent=h?(h.g?'Yes':'Partly'):'No';a.className='ans '+(h?'yes':'no')}
    set('target',fmt(tg));
    set('detail',h?h.n+(h.g?' (nationwide)':' (some regions only)'):'No public holiday on this date.');
    var n2=nextOf(D.dates,iso(dn(tg)+1));
    if(n2){var nd=dn(n2[0])-dn(t0);set('nname',n2[1]);set('nwhen',fmt(n2[0]));set('ndays',String(nd));set('nunit',nd===1?'day':'days')}
  }
}

/* event tiles on home / index */
var evs=document.querySelectorAll('[data-dates]');
for(var i=0;i<evs.length;i++){
  var L=evs[i].getAttribute('data-dates').split(','),tt=today(),nx=null;
  for(var j=0;j<L.length;j++){if(L[j]>=tt){nx=L[j];break}}
  var dl=evs[i].querySelector('.dl');
  if(nx&&dl)dl.textContent=inDays(dn(nx)-dn(tt));
}

/* home: pick country + live card */
var sel=$('cs'),go=$('go'),me=$('me');
function setSel(cc){
  if(!sel||!cc)return false;
  for(var i=0;i<sel.options.length;i++){if(sel.options[i].getAttribute('data-cc')===cc){sel.selectedIndex=i;return true}}
  return false;
}
function region(){
  var l=(navigator.languages&&navigator.languages[0])||navigator.language||'',p=l.split('-');
  return p[1]?p[1].toUpperCase():null;
}
function render(C){
  var t=today(C.tz),h=C.h[t],nx=nextOf(C.dates,iso(dn(t)+1));
  var f=$('me-flag');f.src='/flags/'+C.cc.toLowerCase()+'.svg';
  set('me-title','Today in '+C.n);
  var a=$('me-ans');a.textContent=h?(h.g?'Yes, public holiday':'Partly a holiday'):'No public holiday';
  set('me-detail',h?h.n:(nx?'Next: '+nx[1]+' '+inDays(dn(nx[0])-dn(t)):''));
  var g=$('me-go');g.href='/holidays/'+C.slug+'/';
  me.hidden=false;
}
function load(cc){
  fetch('/d/'+cc.toLowerCase()+'.json').then(function(r){return r.json()}).then(render).catch(function(){});
}
if(sel&&go){
  go.onclick=function(){if(sel.value)location.href=sel.value};
  if(me){
    sel.onchange=function(){var o=sel.options[sel.selectedIndex];if(o&&o.getAttribute('data-cc'))load(o.getAttribute('data-cc'))};
    fetch('/d/tz.json').then(function(r){return r.json()}).then(function(m){
      var z='';try{z=Intl.DateTimeFormat().resolvedOptions().timeZone}catch(e){}
      return m[z]||region();
    }).catch(region).then(function(cc){if(cc&&setSel(cc))load(cc)});
  }else{
    var r=region();if(r)setSel(r);
  }
}

/* country filter */
var cf=$('cf');
if(cf){cf.oninput=function(){
  var q=cf.value.toLowerCase(),items=document.querySelectorAll('#clist li');
  for(var i=0;i<items.length;i++)items[i].style.display=items[i].textContent.toLowerCase().indexOf(q)>-1?'':'none';
}}

/* contact form */
var cform=$('cform'),formT=Date.now();
if(cform&&window.fetch){
  cform.addEventListener('submit',function(e){
    e.preventDefault();
    var st=$('cstatus'),btn=cform.querySelector('button');
    var data={};new FormData(cform).forEach(function(v,k){data[k]=v});
    if(data.website||data.botcheck||(Date.now()-formT)<3000){st.className='ok';st.textContent='Thank you. Your message was sent.';return}
    if(!data['h-captcha-response']){st.className='err';st.textContent='Please tick the box to show you are not a robot.';return}
    st.className='';st.textContent='Sending…';btn.disabled=true;
    fetch(cform.action,{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(data)})
      .then(function(r){return r.json()})
      .then(function(j){
        if(j.success){st.className='ok';st.textContent='Thank you. Your message was sent.';cform.reset()}
        else{st.className='err';st.textContent='Sorry, the message could not be sent. Please try again later.'}
      })
      .catch(function(){st.className='err';st.textContent='Sorry, the message could not be sent. Please check your connection and try again.'})
      .then(function(){btn.disabled=false});
  });
}

/* e-mail link */
var em=document.querySelectorAll('.eml');
for(var q=0;q<em.length;q++){
  var a=document.createElement('a'),addr=em[q].getAttribute('data-u')+'@'+em[q].getAttribute('data-d');
  a.href='mailto:'+addr;a.textContent=addr;em[q].parentNode.replaceChild(a,em[q]);
}
})();
