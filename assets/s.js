(function(){
var el=document.getElementById('d');
function $(i){return document.getElementById(i)}
function set(i,t){var e=$(i);if(e)e.textContent=t}
function dn(s){var p=s.split('-');return Date.UTC(+p[0],+p[1]-1,+p[2])/864e5}
function today(tz){
  try{return new Intl.DateTimeFormat('en-CA',{timeZone:tz||undefined,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}
  catch(e){var d=new Date();return d.getFullYear()+'-'+('0'+(d.getMonth()+1)).slice(-2)+'-'+('0'+d.getDate()).slice(-2)}
}
function fmt(s){return new Date(dn(s)*864e5).toLocaleDateString('en-GB',{timeZone:'UTC',weekday:'long',day:'numeric',month:'long',year:'numeric'})}
function plural(n,w){return n+' '+w+(n===1?'':'s')}
function nextOf(list,t){for(var i=0;i<list.length;i++){if(list[i][0]>=t)return list[i]}return null}
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
    var t0=today(D.tz),tg=new Date((dn(t0)+D.offset)*864e5).toISOString().slice(0,10),h=D.h[tg];
    var a=$('ans');
    if(a){
      a.textContent=h?(h.g?'Yes':'Partly'):'No';
      a.className='ans '+(h?'yes':'no');
    }
    set('target',fmt(tg));
    if(h){set('detail',h.n+(h.g?' (nationwide)':' (some regions only)'))}
    else{set('detail','No public holiday on this date.')}
    var n2=nextOf(D.dates,new Date((dn(tg)+1)*864e5).toISOString().slice(0,10));
    if(n2){set('nname',n2[1]);set('nwhen',fmt(n2[0]));set('ndays',plural(dn(n2[0])-dn(t0),'day'))}
  }
}
var sel=$('cs'),go=$('go');
if(sel&&go){
  try{var r=(navigator.language||'').split('-')[1];if(r){for(var i=0;i<sel.options.length;i++){if(sel.options[i].getAttribute('data-cc')===r.toUpperCase()){sel.selectedIndex=i;break}}}}catch(e){}
  go.onclick=function(){if(sel.value)location.href=sel.value};
}
})();
