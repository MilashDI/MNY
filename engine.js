(function(root){
const roles={civil:'Мирный житель',sheriff:'Шериф',mafia:'Мафия',don:'Дон'};
const black=p=>['mafia','don'].includes(p.role);
function create(ids){return {id:Date.now().toString(),created:new Date().toISOString(),phase:'setup',day:-1,roundVersion:2,opener:0,speaker:0,spoken:[],nominated:[],ballot:null,voteDisqualifications:[],nights:[],log:[],winner:null,timer:{elapsed:0,started:null},seats:ids.map((id,i)=>({id,number:i+1,role:'civil',alive:true,fouls:0,extraScoreTenths:0,extraScoreComment:'',technicalFoul:false,muteDay:null,reason:null}))};}
function nextAlive(g,n){for(let k=1;k<=10;k++){let i=(n+k)%10;if(g.seats[i].alive)return i;}return null;}
function startDay(g){g.opener=g.day<0?(g.seats[0].alive?0:nextAlive(g,0)):nextAlive(g,g.opener);g.day++;g.phase='day';g.speaker=g.opener;g.spoken=[];g.nominated=[];g.ballot=null;}
function foul(g,i){const p=g.seats[i];if(!p.alive||p.fouls>=3)return;p.fouls++;if(p.fouls===3)p.muteDay=g.phase==='day'&&!g.spoken.includes(i)?g.day:g.day+1;}
function remove(g,i,reason){g.seats[i].alive=false;g.seats[i].reason=reason;}
function winner(g){const alive=g.seats.filter(p=>p.alive),b=alive.filter(black).length;return b===0?'red':b>=alive.length-b?'black':null;}
function validate(g){const count=r=>g.seats.filter(p=>p.role===r).length;return g.seats.length===10&&count('civil')===6&&count('sheriff')===1&&count('mafia')===2&&count('don')===1;}
function result(g){const b=g.ballot,values=b.candidates.map(i=>Number(b.votes[i]||0));const max=Math.max(...values);return b.candidates.filter((i,k)=>values[k]===max);}
function validExtraScore(value){return Number.isInteger(value)&&value>=-40&&value<=20&&(value<=0||value%2===0)}
function adjustExtraScore(value,direction){if(!validExtraScore(value))value=0;const next=value+(direction>0?(value<0?1:2):(value>0?-2:-1));return Math.max(-40,Math.min(20,next))}
function firstNightVictim(g){const first=g.nights.find(n=>n.day===0);return !first||first.missed||!Number.isInteger(first.kill)||first.kill<0||first.kill>=g.seats.length?null:first.kill}
function firstKilled(g){const victim=firstNightVictim(g);if(victim===null)return null;const second=g.nights.find(n=>n.day===1),departures=second?.nonNightDepartures??g.seats.filter(p=>!p.alive&&/^(Удалён|Заголосован|Поднят при равенстве|4 фола)/.test(p.reason||'')).length;return departures>=2?null:victim}
function bestMove(g,p){const owner=firstKilled(g);if(owner===null||g.seats[owner]!==p)return {hits:0,tenths:0};const picks=[...new Set(g.bestMoves?.[owner]||[])].filter(i=>Number.isInteger(i)&&g.seats[i]).slice(0,3),hits=picks.filter(i=>black(g.seats[i])).length;return {hits,tenths:picks.length===3?(hits===3?8:hits===2?4:0):0}}
function drawSurvivor(g,p){return Array.isArray(g.drawAlive)?g.drawAlive.includes(g.seats.indexOf(p)):p.alive}
function canAssignExtra(g,p){return !(g.winner==='draw'&&drawSurvivor(g,p))}
function extraScoreLimit(g,p){if(!canAssignExtra(g,p))return 0;return g.seats[firstNightVictim(g)]===p?16-bestMove(g,p).tenths:20}
function effectiveExtraScore(g,p){if(!canAssignExtra(g,p))return 0;return Math.min(validExtraScore(p.extraScoreTenths)?p.extraScoreTenths:0,extraScoreLimit(g,p))}
function score(g,p){const base=g.winner==='draw'?(drawSurvivor(g,p)?5:10):g.winner&&((black(p)&&g.winner==='black')||(!black(p)&&g.winner==='red'))?20:(g.winner?10:0),lh=bestMove(g,p),extra=effectiveExtraScore(g,p);return {base:base/10,bestMove:lh.tenths/10,hits:lh.hits,extra:extra/10,total:(base+extra+lh.tenths)/10}}
function isDraw(g){const nights=g.nights.filter(n=>n.day>=0).slice(-3);if(nights.length!==3||nights[1].day!==nights[0].day+1||nights[2].day!==nights[1].day+1||!Array.isArray(nights[0].startedAlive))return false;const current=g.seats.flatMap((p,i)=>p.alive?[i]:[]);return current.length===nights[0].startedAlive.length&&current.every(i=>nights[0].startedAlive.includes(i))}

const api={roles,black,create,nextAlive,startDay,foul,remove,winner,validate,result,validExtraScore,adjustExtraScore,score,firstKilled,firstNightVictim,bestMove,canAssignExtra,extraScoreLimit,effectiveExtraScore,isDraw,drawSurvivor};if(typeof module!=='undefined')module.exports=api;root.MNY=api;
})(typeof window!=='undefined'?window:globalThis);
